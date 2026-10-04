"""Original and v2 comparator clients, plus a neutral strict syntax client."""
import importlib.util
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[2]

def load_module(name,path):
    if name in sys.modules:
        module=sys.modules[name]
        if Path(module.__file__).resolve()!=path.resolve():
            raise RuntimeError('Module alias collision: '+name)
        return module
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

# The v2 comparator and original client retain their exact implementation.
STRICT=load_module('neutral_v3_targeted_client',ROOT/'experiments/online_llm_targeted/client.py')
V1Client=STRICT.V1Client
ContractClient=STRICT.ContractClient
FatalAPIError=STRICT.FatalAPIError
write=STRICT.write
FEATURES=STRICT.FEATURES
FORMAT_CONTRACT=STRICT.FORMAT_CONTRACT
compile_rule=STRICT.compile_rule
validate_candidates=STRICT.validate_candidates

NEUTRAL_APPENDIX='\nOUTPUT SYNTAX APPENDIX: Return exactly one JSON object with only the key "candidates".\n"candidates" must be an array of exactly candidate_count objects. Each candidate has exactly "explanation" (a string) and "rules" (an array).\nEach candidate has 1..4 total rules across all agents. Every rule has exactly "when" and "delta", both JSON strings containing expressions.\nThe only legal feature names are agent, inventory, backlog, pipeline, arrival, incoming, recent, baseline, growth, happo.\nInside expression strings use Python True/False and and/or/not. The surrounding response must remain JSON.\nKeep the original DSL operators, min/max/abs functions, and original correction and order bounds. No assignments, indexing, imports, other functions or additional feature names.\nBefore returning, check the requested candidate count, total rule count, exact object keys, expression string types and legal features.\n'


class NeutralClient(ContractClient):
    """Strict v2 transport and validation; neutral appendix in format repairs."""
    def generate(self,context,count,identity,stage):
        messages=[dict(role='system',content=self.system),
                  dict(role='user',content=json.dumps(dict(context,candidate_count=count),ensure_ascii=False))]
        for attempt in range(2):
            if self.episode_http>=16:
                raise RuntimeError('Episode HTTP budget exceeded')
            self.episode_http+=1
            body=dict(model=self.model,messages=messages,response_format={'type':'json_object'},
                      thinking={'type':'disabled'},temperature=.2,max_tokens=3000)
            record=dict(**identity,stage=stage,attempt=attempt+1,request=body,status='started')
            self.records.append(record);self.save()
            started=time.perf_counter();result=None;repair=False;fatal=None
            try:
                request=urllib.request.Request('https://api.deepseek.com/chat/completions',data=json.dumps(body).encode(),
                    headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
                with urllib.request.urlopen(request,timeout=30) as response:
                    raw=response.read().decode('utf-8')
                record['raw_response']=raw
                try:
                    response=json.loads(raw);record['response']=response;record['usage']=response.get('usage')
                    choice=response['choices'][0]
                    if choice['finish_reason']!='stop':
                        raise ValueError('Incomplete output')
                    document=json.loads(choice['message']['content'])
                    if not isinstance(document,dict) or set(document)!={'candidates'}:
                        raise ValueError('Top-level object must contain only candidates')
                    values=document['candidates'];validate_candidates(values,count)
                    result=[dict(id=f"event{identity['event']}_{stage}_{i}",rule=value,compiled=compile_rule(value)) for i,value in enumerate(values)]
                    record['candidates']=values;record['status']='valid'
                except Exception as exc:
                    record.update(status='failed',failure=str(exc)[:400],failure_kind='format');repair=True
                    choices=record.get('response',{}).get('choices') or []
                    original_content=choices[0].get('message',{}).get('content',raw) if choices else raw
                    messages=messages[:2]+[dict(role='assistant',content=original_content),dict(role='user',content=
                        'Repair only JSON/DSL contract errors in the preceding answer. '+record['failure']+
                        f' Return exactly{count} candidates. Allowed names: '+', '.join(FEATURES)+'. '+NEUTRAL_APPENDIX)]
            except urllib.error.HTTPError as exc:
                record.update(status='failed',failure=f'HTTP_{exc.code}',failure_kind='http')
                if exc.code in (401,402,403):
                    fatal=FatalAPIError(f'API authentication/balance/permission failure HTTP_{exc.code}')
                try:
                    record['error_response']=exc.read().decode('utf-8',errors='replace')[:20000]
                except Exception:
                    record['error_response']='[unreadable HTTP error body]'
            except Exception as exc:
                record.update(status='failed',failure=type(exc).__name__,failure_kind='transport')
            finally:
                record['seconds']=time.perf_counter()-started
                for name in ('raw_response','error_response','failure'):
                    if isinstance(record.get(name),str):
                        record[name]=record[name].replace(self.key,'[REDACTED]')
                self.save()
            if fatal:
                raise fatal
            if result is not None:
                return result
            if not repair:
                break
        return []
