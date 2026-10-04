"""Original v1 client plus an isolated strict output-contract variant."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/deepseek_refinement'))
from shadow import compile_rule


def load_original(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


ORIGINAL=load_original('targeted_original_client',ROOT/'experiments/online_llm/client.py')
V1Client=ORIGINAL.Client
FatalAPIError=ORIGINAL.FatalAPIError
write=ORIGINAL.write
FEATURES=('agent','inventory','backlog','pipeline','arrival','incoming','recent','baseline','growth','happo')
FORMAT_CONTRACT='''
OUTPUT CONTRACT: Return exactly one JSON object with only the key "candidates".
"candidates" is an array of candidate_count objects, each with exactly "explanation" (a string) and "rules" (an array of1..4 objects).
Every rule has exactly "when" and "delta", BOTH JSON strings containing DSL expressions.
Each candidate has at most4 TOTAL rules across ALL3 agents, not4 rules per agent. Prefer3 rules with agent==0/1/2 and conditional delta expressions over6 or more separate node guards.
EXACT legal feature names: agent, inventory, backlog, pipeline, arrival, incoming, recent, baseline, growth, happo.
Use no other variable names: inventory_position, local_demand, pipeline_total, report_age, period, demand, target, order and node are NOT DSL features. Pipeline slots may appear in context but not as DSL variables.
Constants and operators stay in the original DSL; no assignment, arbitrary functions, indexing or imports.
Valid one-candidate example (repeat distinct objects to satisfy candidate_count):
{"candidates":[{"explanation":"Zero correction is permitted","rules":[{"when":"True","delta":"0"}]}]}
Valid state predicate example: {"when":"agent == 0 and backlog > 5 and pipeline < 20","delta":"min(2, backlog / 4)"}.
Inside expression STRINGS use Python True/False, and/or/not; do not use lowercase true or JSON operators. The top-level response remains JSON.
Before responding verify candidate_count, rule counts, exact object keys, string expressions, and every variable against the ten-name list. Formatting is not evidence of effectiveness.
'''


def validate_candidates(values,count):
    if not isinstance(values,list) or len(values)!=count:
        raise ValueError(f'candidates must be an array of exactly{count} objects')
    for value in values:
        if not isinstance(value,dict) or set(value)!={'explanation','rules'} or not isinstance(value['explanation'],str):
            raise ValueError('Each candidate needs exactly explanation:string and rules:array')
        compile_rule(value)


class ContractClient(V1Client):
    """Same transport/budgets as v1, with explicit JSON and DSL format repairs."""
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
                        f' Return exactly{count} candidates. Allowed names: '+', '.join(FEATURES)+'. '+FORMAT_CONTRACT)]
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
