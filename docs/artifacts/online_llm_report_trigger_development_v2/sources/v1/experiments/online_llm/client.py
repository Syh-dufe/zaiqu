"""Bounded synchronous API client. Logs contain no authorization header."""
import json
import os
import time
import urllib.error
import urllib.request
from shadow import compile_rule


class FatalAPIError(RuntimeError):
    """Authentication, balance or permission failure stops the entire batch."""


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


class Client:
    def __init__(self, output, system, model='deepseek-flash'):
        self.output = output
        self.system = system
        self.model = model
        self.records = []
        self.episode_http = 0
        self.key = os.environ.get('DEEPSEEK_API_KEY')
        if not self.key:
            raise ValueError('DEEPSEEK_API_KEY missing')
        self.save()

    def save(self):
        # Scrub every nested response and any response text in a repair request.
        value=json.loads(json.dumps(self.records,ensure_ascii=False).replace(self.key,'[REDACTED]'))
        write(self.output / 'calls.json',value)

    def reset_episode(self):
        self.episode_http = 0

    def generate(self, context, count, identity, stage):
        """One semantic request, at most one format repair. Transport errors fall back."""
        messages = [dict(role='system', content=self.system),
                    dict(role='user', content=json.dumps(dict(context, candidate_count=count), ensure_ascii=False))]
        for attempt in range(2):
            if self.episode_http >= 16:
                raise RuntimeError('Episode HTTP budget exceeded')
            self.episode_http += 1
            body = dict(model=self.model, messages=messages, response_format={'type':'json_object'},
                        thinking={'type':'disabled'}, temperature=.2, max_tokens=3000)
            record = dict(**identity, stage=stage, attempt=attempt+1, request=body, status='started')
            self.records.append(record)
            self.save()
            started = time.perf_counter()
            result = None
            repair = False
            fatal = None
            try:
                request = urllib.request.Request('https://api.deepseek.com/chat/completions',
                    data=json.dumps(body).encode(), headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
                with urllib.request.urlopen(request, timeout=30) as response:
                    raw = response.read().decode('utf-8')
                record['raw_response'] = raw
                try:
                    response = json.loads(raw)
                    record['response'] = response
                    record['usage'] = response.get('usage')
                    choice = response['choices'][0]
                    if choice['finish_reason'] != 'stop':
                        raise ValueError('Incomplete output')
                    values = json.loads(choice['message']['content'])['candidates']
                    if not isinstance(values, list) or len(values) != count:
                        raise ValueError('Wrong candidate count')
                    result = [dict(id=f"event{identity['event']}_{stage}_{i}", rule=value,
                                   compiled=compile_rule(value)) for i, value in enumerate(values)]
                    record['candidates'] = values
                    record['status'] = 'valid'
                except Exception as exc:
                    record.update(status='failed', failure=str(exc)[:400], failure_kind='format')
                    repair = True
                    original_content = record.get('response',{}).get('choices',[{}])[0].get('message',{}).get('content',raw)
                    messages = messages[:2] + [dict(role='assistant',content=original_content),dict(role='user', content='Repair the JSON/DSL format only. '+record['failure']+
                        f' Return exactly {count} candidates with valid expressions. Use True for an unconditional predicate.')]
            except urllib.error.HTTPError as exc:
                record.update(status='failed', failure=f'HTTP_{exc.code}', failure_kind='http')
                if exc.code in (401, 402, 403):
                    fatal = FatalAPIError(f'API authentication/balance/permission failure HTTP_{exc.code}')
                try:
                    record['error_response'] = exc.read().decode('utf-8', errors='replace')[:20000]
                except Exception:
                    record['error_response'] = '[unreadable HTTP error body]'
            except Exception as exc:
                record.update(status='failed', failure=type(exc).__name__, failure_kind='transport')
            finally:
                record['seconds'] = time.perf_counter()-started
                # Defense against a server reflecting a credential in an error body.
                for name in ('raw_response','error_response','failure'):
                    if isinstance(record.get(name),str):
                        record[name] = record[name].replace(self.key,'[REDACTED]')
                self.save()
            if fatal:
                raise fatal
            if result is not None:
                return result
            if not repair:
                break
        return []
