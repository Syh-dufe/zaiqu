"""Bounded offline operator discovery using two model requests and past fitness."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.error
from run import ROOT, SYSTEM, write, compile_rule


def main():
    root=ROOT/'results/deepseek_refinement';out=root/'operator_discovery_v1'
    if out.exists():raise SystemExit('Refuse overwrite')
    key=os.environ.get('DEEPSEEK_API_KEY')
    if not key:raise SystemExit('Missing API key')
    old=sum(sum(not c.get('replayed',False) for c in json.loads(p.read_text(encoding='utf-8'))) for p in root.glob('*/calls.json'))
    if old+2>120:raise SystemExit('Series budget exceeded')
    out.mkdir(parents=True);calls=[]
    offline=SYSTEM.replace('You are notified a demand emergency HAS occurred. Future demand, duration and magnitude are unknown. You only see past demand and current state. Do not infer knowledge of the event end. HAPPO does not train.',
        'You design a reusable OPERATOR LIBRARY OFFLINE. Provided fitness comes from completed development simulations, not a future deployment. Generate generic state-dependent operators that transfer to unknown future demand emergencies. Do not hardcode dates, traces or future event timing. HAPPO remains frozen. Online causal forecasts will select or reject operators; no event-time model request is claimed.')
    def request(context,count):
        body=dict(model='deepseek-flash',messages=[dict(role='system',content=offline),dict(role='user',content=json.dumps(dict(context,candidate_count=count)))],
                  response_format={'type':'json_object'},thinking={'type':'disabled'},temperature=.2,max_tokens=3000)
        record=dict(index=len(calls),request=body,status='started');calls.append(record);write(out/'calls.json',calls)
        start=time.perf_counter();valid=[]
        try:
            req=urllib.request.Request('https://api.deepseek.com/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=30) as f:response=json.load(f)
            record['response']=response;choice=response['choices'][0]
            if choice['finish_reason']!='stop':raise ValueError('Incomplete output')
            candidates=json.loads(choice['message']['content'])['candidates'];record['candidates']=candidates
            if len(candidates)!=count:raise ValueError('Unexpected count')
            for i,r in enumerate(candidates):
                try:compile_rule(r);valid.append(r)
                except Exception as exc:record.setdefault('invalid_candidates',[]).append(dict(index=i,failure=type(exc).__name__))
            record['status']='valid' if valid else 'failed'
        except urllib.error.HTTPError as exc:record['status']='failed';record['failure']='HTTP_'+str(exc.code)
        except Exception as exc:record['status']='failed';record['failure']=type(exc).__name__
        record['seconds']=time.perf_counter()-start;write(out/'calls.json',calls)
        print('API',record['index'],record['status'],flush=True);return valid
    diagnosis=json.loads((root/'predictor_merton_diagnosis/summary.json').read_text())
    context=dict(past_development=diagnosis,
        forecast='Approximate public Merton log transition from last observed integer demand+.5; six20-period paths,3search+3holdout',
        control='First5 forecast periods use operator; tail frozen HAPPO. Reselect every5 periods, require mean system cost>=1% reduction and no downstream backlog increase in both batches.',
        failure_to_avoid='Some legal rules caused extra upstream stock or propagated backlog after short interventions. Avoid starving downstream by aggressive cuts, and avoid replenishing an already sufficient pipeline.',
        objective='Design3 diverse reusable conservative operators, not3 descriptions of the same rule. All node costs matter. Do not simply copy a positive-only manual heuristic.')
    initial=request(context,3);write(out/'initial_library.json',dict(candidates=initial,stage='offline_development'))
    command=[sys.executable,'-u',str(Path(__file__).with_name('run.py')),'--run-name','library_development_v1','--cases','2',
             '--demand-seed','20261062','--event-seed','20261063','--correction-periods','5','--predictor','merton',
             '--operator-library',str(out/'initial_library.json')]
    with (out/'development.log').open('w',encoding='utf-8') as f:result=subprocess.run(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    if result.returncode:write(out/'failed.json',dict(returncode=result.returncode));raise SystemExit(result.returncode)
    p=root/'library_development_v1'
    result=subprocess.run([sys.executable,str(Path(__file__).with_name('summarize.py')),str(p)],cwd=ROOT,capture_output=True,text=True)
    if result.returncode:raise SystemExit(result.stderr)
    summary=json.loads((p/'summary.json').read_text());scores=json.loads((p/'scores.json').read_text())
    refined=request(dict(context,past_completed_fitness=summary,previous_candidates=initial,
                search_examples=[{'period':s['period'],'trace':s['trace'],'search':s['search']} for s in scores if s['group']=='llm_library'][:8]),1)
    write(out/'final_library.json',dict(candidates=initial+refined,stage='frozen_for_future_confirmation',initial_count=len(initial),refined_count=len(refined)))
    write(out/'completed.json',dict(api_calls=len(calls),calls_before=old,initial=len(initial),refined=len(refined),
            fitness_scope='two development traces; no independent test demands provided to LLM'))
    print('OPERATOR_DISCOVERY_COMPLETED',flush=True)


if __name__=='__main__':main()
