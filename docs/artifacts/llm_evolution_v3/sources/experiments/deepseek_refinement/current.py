"""Current-report environment discovery across five frozen models; no online API."""
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import numpy as np
from run import ROOT, SYSTEM, compile_rule

OUT = ROOT / 'results/llm_current_v2'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def training(seed):
    return ROOT / 'results/learning_curve' / ('curve_seed11_until_stable_v1' if seed == 11 else f'curve_seed{seed}_formal_v1')


def generate(ds, es, used):
    sys.path.insert(0, str(ROOT / 'external/liu-inventory'))
    from envs.generator import merton
    np.random.seed(ds)
    base = [merton(200,20).demand_list for _ in range(4)]
    rng = random.Random(es)
    events = [{'start_index': rng.randint(60,100), 'duration': rng.randint(20,40)} for _ in base]
    for trace in base:
        signature = tuple(trace[:200])
        if signature in used:
            raise RuntimeError('Demand already used; do not regenerate selectively')
        used.add(signature)
    shock = [[min(20, math.ceil(1.5*v)) if e['start_index'] <= i < e['start_index'] + e['duration'] else v for i,v in enumerate(trace)] for trace,e in zip(base, events)]
    return {'demand_seed':ds,'event_seed':es,'base':base,'shock':shock,'events':events}


def evaluate(label, library, inputs, random_group=False):
    fitness = []; sources = []; feedback = []
    methods = ['happo','llm_library'] + (['random_screen'] if random_group else [])
    for seed in range(11,16):
        for number, source in enumerate(inputs,1):
            name = f'{label}_seed{seed}_batch{number}'
            target = OUT / name
            if target.exists(): raise RuntimeError('Evaluation already exists: '+name)
            command = [sys.executable,'-u',str(Path(__file__).with_name('run.py')),'--run-name',name,'--output-root',str(OUT),
                       '--training-directory',str(training(seed)),'--input-file',str(source),'--cases','4',
                       '--operator-library',str(library),'--methods',*methods,'--correction-periods','5','--predictor','merton','--report-interval','3']
            write(OUT/'progress.json',{'status':'evaluating','label':label,'seed':seed,'batch':number,'pid':os.getpid()})
            with (OUT / f'{name}.log').open('w',encoding='utf-8') as log:
                process = subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            if process.returncode: raise RuntimeError('Evaluation failed: '+name)
            done = read(target/'completed.json')
            expected_hash = read(training(seed)/'completion_audit.json')['model_matches']['official_best']['sha256']
            assert not done['runtime_failures'] and done['calls']==done['training_updates']==0
            assert all(c['unchanged'] and c['before']==expected_hash for c in done['parameter_checks'].values())
            episodes = read(target/'episodes.json')
            for trace in range(4):
                for group in methods:
                    episode = next(e for e in episodes if e['trace']==trace and e['group']==group and e['scenario']=='shock')
                    base = next(e for e in episodes if e['trace']==trace and e['group']==group and e['scenario']=='base')
                    ref = next(e for e in episodes if e['trace']==trace and e['group']=='happo' and e['scenario']=='base')
                    assert all(base[k]==ref[k] for k in ('cost','downstream_backlog'))
                    fitness.append({'seed':seed,'trajectory':(number-1)*4+trace,'group':group,'cost':episode['cost'],'backlog':episode['downstream_backlog']})
            scores = read(target/'scores.json')
            feedback.extend([{'seed':seed,'group':s['group'],'search':s['search'],'chosen':s['chosen'],
                              'validation_zero':s.get('validation_zero'),'validation_candidate':s.get('validation_candidate')} for s in scores[:3]])
            sources.append({'path':str(target),'input_sha256':digest(source),'model_sha256':expected_hash})
    groups = {g: [] for g in methods}; deltas=[]; worst=[]; per_seed=[]
    for seed in range(11,16):
        local=[]
        for trace in range(len(inputs)*4):
            pair = {g: next(r for r in fitness if r['seed']==seed and r['trajectory']==trace and r['group']==g) for g in methods}
            delta = [pair['llm_library'][k]-pair['happo'][k] for k in ('cost','backlog')]
            deltas.append(delta);local.append(delta)
            worst.append({'seed':seed,'trajectory':trace,'delta':delta,'happo':pair['happo'],'llm':pair['llm_library']})
            for g in methods: groups[g].append([pair[g]['cost'],pair[g]['backlog']])
        per_seed.append({'seed':seed,'mean_delta':np.mean(local,axis=0).tolist()})
    summary = {'means':{g:np.mean(v,axis=0).tolist() for g,v in groups.items()},'mean_delta':np.mean(deltas,axis=0).tolist(),
               'per_seed':per_seed,'worst_cases':sorted(worst,key=lambda r:r['delta'][0],reverse=True)[:5],
               'predicted_selection_examples':feedback,'fitness':fitness,'sources':sources}
    write(OUT/f'{label}_summary.json',summary)
    return summary


def main():
    if OUT.exists(): raise RuntimeError('Refuse overwrite/repeated launch; inspect existing progress')
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key: raise RuntimeError('Missing configured API key')
    OUT.mkdir(parents=True)
    calls = []; history = []; used = set()
    for parent in (ROOT/'results',ROOT/'docs/artifacts'):
        for path in set(parent.rglob('demands.json')) | set(parent.rglob('batch*.json')):
            data = read(path)
            if isinstance(data,dict): used.update(tuple(t[:200]) for t in data.get('base',[]))
    sources = [Path(__file__),Path(__file__).with_name('run.py'),Path(__file__).with_name('shadow.py'),Path(__file__).with_name('reports.py'),ROOT/'experiments/deepseek_pilot/rules.py']
    hashes = {str(p.relative_to(ROOT)):digest(p) for p in sources}
    write(OUT/'manifest.json',{'rounds_first_block':6,'training_seeds':list(range(11,16)),'source_sha256':hashes,
                             'api_total_limit':None,'format_attempts_per_round':3,'development_demand_seed':20270101,
                             'new_confirmation_seeds':list(range(20270201,20270211)),'prior_results_are_development':True})
    srcout=OUT/'sources';srcout.mkdir()
    for p in sources: shutil.copy2(p,srcout/('_'.join(p.relative_to(ROOT).parts)))
    development = OUT/'development_inputs.json';write(development,generate(20270101,20270102,used))
    old = ROOT/'docs/artifacts/operator_discovery_v1/repaired_library.json'
    initial = evaluate('old_development',old,[development],True)
    incumbent = old; best = initial
    history.append({'label':'old_development','library':str(old),'summary':initial})
    system = SYSTEM + '''
You are designing an OFFLINE reusable library for the CURRENT periodic-report environment across FIVE frozen HAPPO models, seeds11..15. No model update or event-time API request.
IMPORTANT: recent and baseline derive from DELIVERED reports: every3 periods the preceding3 actual external demands are averaged, this mean is repeated3 times in reconstructed history, available at the next decision. Undelivered demand is not available. Growth thus may react late. Node0 incoming is last delivered reconstructed external demand; upstream incoming is preceding actual downstream order, not current external demand. inventory/backlog/pipeline/arrival and current proposed happo order are observed globally without report delay.
The emergency notification is available after two completed event periods. Rules know only that notification arrived, never actual remaining event time, multiplier, start or end.
Online screening uses6 approximate20-period Merton forecast paths,3 search+3 independent review, correction first5 periods, reselect every5. Require1percent mean cost reduction and no mean downstream backlog increase in both batches, otherwise zero. Predictor may be miscalibrated after shocks; candidate overreactions and forecast/realized mismatch matter.
Return EXACTLY3 candidates, EACH one to four ordered rules. No rule outside the DSL. To make unconditional predicates use True, NEVER lowercase true. No terminal zero rule is needed. Guards must prevent division by zero. Distinguish three mechanisms; all-zero is legal but not an improvement.
Completed development feedback may include random constant candidates; if learning from them, explicitly explain this source, then design state-dependent mechanisms. Do not hardcode seed IDs, dates, trace, time or unseen future. Favor robust coordination and avoid replacing HAPPO wholesale.'''
    try:
        for iteration in range(1,7):
            candidates = None
            for attempt in range(3):
                context = {'round':iteration,'candidate_count':3,'current_incumbent':read(incumbent),
                           'feedback':history[-3:],'earlier_formal_diagnosis':read(ROOT/'results/formal_evaluation/bc_analysis_v1/summary.json')['main'],
                           'random_diagnostic_rules':read(ROOT/'results/formal_evaluation/stage_c_seed11_k3_v1/stage_c_seed11_k3_v1_batch1/random_library.json'),
                           'previous_format_failure':calls[-1].get('failure') if calls and calls[-1]['status']=='failed' else None}
                body = {'model':os.environ.get('DEEPSEEK_MODEL','deepseek-flash'),'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(context)}],
                        'response_format':{'type':'json_object'},'thinking':{'type':'disabled'},'temperature':.3,'max_tokens':4000}
                record = {'round':iteration,'attempt':attempt+1,'request':body,'status':'started'}
                calls.append(record);write(OUT/'calls.json',calls);write(OUT/'progress.json',{'status':'requesting','round':iteration,'attempt':attempt+1,'pid':os.getpid()})
                started=time.perf_counter()
                try:
                    request=urllib.request.Request('https://api.deepseek.com/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
                    with urllib.request.urlopen(request,timeout=90) as response: result=json.load(response)
                    record['response']=result;record['usage']=result.get('usage')
                    choice=result['choices'][0]
                    if choice['finish_reason']!='stop': raise ValueError('Incomplete output')
                    proposed=json.loads(choice['message']['content'])['candidates']
                    if len(proposed)!=3: raise ValueError('Exactly3 candidates required')
                    for rule in proposed: compile_rule(rule)
                    candidates=proposed;record['status']='valid'
                except urllib.error.HTTPError as exc:
                    record['status']='failed';record['failure']='HTTP_'+str(exc.code)
                    if exc.code in (401,402,403):
                        write(OUT/'calls.json',calls);raise RuntimeError('API authentication/balance/permission failure') from None
                except Exception as exc:
                    record['status']='failed';record['failure']=str(exc)[:400]
                record['seconds']=time.perf_counter()-started;write(OUT/'calls.json',calls)
                print('API',iteration,attempt+1,record['status'],flush=True)
                if candidates is not None: break
            if candidates is None: raise RuntimeError('Three invalid responses; diagnose rather than unlimited retry')
            library=OUT/f'round{iteration}_library.json';write(library,{'candidates':candidates,'stage':'current_environment_development','iteration':iteration})
            for rel,value in hashes.items():
                if digest(ROOT/rel)!=value: raise RuntimeError('Source changed while running')
            summary=evaluate(f'round{iteration}_development',library,[development])
            history.append({'label':f'round{iteration}','library':str(library),'summary':summary});write(OUT/'history.json',history)
            delta=summary['mean_delta'];current=best['mean_delta']
            if delta[1]<=0 and (current[1]>0 or delta[0]<current[0]): incumbent=library;best=summary
            print('ROUND',iteration,'delta',delta,'incumbent',incumbent.name,flush=True)
        frozen=OUT/'frozen_library.json';shutil.copy2(incumbent,frozen)
        write(OUT/'frozen_manifest.json',{'library_sha256':digest(frozen),'selected_from':str(incumbent),'development_summary':best,
                                        'old_library_sha256':digest(old),'criterion':'Mean downstream backlog delta<=0, then minimum mean cost delta; old library retained if no eligible replacement'})
        confirm=OUT/'confirmation_inputs';confirm.mkdir();paths=[]
        for number in range(1,6):
            path=confirm/f'batch{number}.json';write(path,generate(20270199+2*number,20270200+2*number,used));paths.append(path)
        write(confirm/'manifest.json',{'frozen_library_sha256':digest(frozen),'inputs':[{ 'path':str(p),'sha256':digest(p)} for p in paths],
                                      'created_after_freeze':True,'no_feedback_to_llm':True})
        result=evaluate('confirmation_new',frozen,paths,True)
        previous=evaluate('confirmation_old',old,paths)
        sys.path.insert(0,str(ROOT/'experiments/formal_evaluation'))
        from analyze_multi import compare
        def matrix(summary,group):
            return np.array([[next([r['cost'],r['backlog']] for r in summary['fitness'] if r['seed']==seed and r['trajectory']==trace and r['group']==group) for trace in range(20)] for seed in range(11,16)])
        baseline=matrix(result,'happo');assert np.array_equal(baseline,matrix(previous,'happo'))
        summary={'new_vs_happo':compare(baseline,matrix(result,'llm_library')),'new_vs_old':compare(matrix(previous,'llm_library'),matrix(result,'llm_library')),
                 'new_vs_random':compare(matrix(result,'random_screen'),matrix(result,'llm_library')),'api_requests':len(calls),
                 'api_failures':sum(c['status']=='failed' for c in calls),'usage':[c.get('usage') for c in calls],
                 'selection_is_development_only':True,'confirmation_episodes':1000,'duplicate_happo_audit_episodes':200,
                 'claim_limit':'Two metrics per comparison; additional comparisons descriptive, not jointly corrected. Library selection used4 development traces, overfitting risk remains.'}
        write(OUT/'confirmation_summary.json',summary);write(OUT/'completed.json',{'status':'completed','selected_library':str(incumbent),'summary':summary})
        print('CURRENT_ENVIRONMENT_ITERATION_COMPLETED',flush=True)
    except Exception as exc:
        write(OUT/'failed.json',{'failure':str(exc),'original_outputs_preserved':True});raise


if __name__=='__main__':main()
