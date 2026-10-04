"""Small reflective population search; queued behind the untouched v2 run."""
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import sys
import time
import urllib.request
import urllib.error
import numpy as np
import current as runner
from rules import rule_delta, bounded_order

ROOT=runner.ROOT
OUT=ROOT/'results/llm_evolution_v3'


def write(path,data): runner.write(path,data)
def read(path): return runner.read(path)


def probes():
    rng=random.Random(20270401);result=[]
    for _ in range(256):
        recent=rng.choice([0.,1.,3.,6.,10.,15.,20.]);baseline=rng.choice([1.,3.,6.,10.,20.])
        for agent in range(3):
            result.append(dict(agent=agent,inventory=rng.randint(0,80),backlog=rng.randint(0,50),pipeline=rng.randint(0,80),
                               arrival=rng.randint(0,20),incoming=rng.randint(0,20),recent=recent,baseline=baseline,
                               growth=recent/baseline,happo=rng.randint(0,20)))
    return result


def fingerprint(library,states):
    if len(library.get('candidates',[]))!=3: raise ValueError('Need exactly3 candidates')
    individual=[]
    for candidate in library['candidates']:
        compiled=runner.compile_rule(candidate)
        actions=[bounded_order(state['happo'],rule_delta(compiled,state)) for state in states]
        individual.append(hashlib.sha256(json.dumps(actions).encode()).hexdigest())
    return hashlib.sha256(json.dumps(sorted(individual)).encode()).hexdigest()


def main():
    if OUT.exists(): raise RuntimeError('Already registered; do not duplicate')
    key=os.environ.get('DEEPSEEK_API_KEY')
    if not key: raise RuntimeError('Missing API key')
    OUT.mkdir(parents=True);runner.OUT=OUT
    write(OUT/'progress.json',{'status':'waiting_v2','pid':os.getpid()})
    calls=[];archive=[];memory=[];seen=set();states=probes();write(OUT/'behavior_probes.json',states)
    source_files=[Path(__file__),Path(runner.__file__),ROOT/'experiments/deepseek_refinement/run.py',ROOT/'experiments/deepseek_refinement/shadow.py',ROOT/'experiments/deepseek_refinement/reports.py',ROOT/'experiments/deepseek_pilot/rules.py']
    hashes={str(p.relative_to(ROOT)):runner.digest(p) for p in source_files}
    write(OUT/'manifest.json',{'source_sha256':hashes,'generations':3,'training_seeds':list(range(11,16)),
                              'probe_seed':20270401,'development_seeds':[20270301,20270302],
                              'internal_validation_seeds':[20270303,20270304],'test_seeds':list(range(20270501,20270511)),
                              'api_total_limit':None,'prior_v2_test_excluded_from_feedback':True})
    try:
        while not (ROOT/'results/llm_current_v2/completed.json').exists():
            if (ROOT/'results/llm_current_v2/failed.json').exists(): raise RuntimeError('v2 failed; diagnose before starting dependent work')
            time.sleep(15)
        used=set()
        for parent in (ROOT/'results',ROOT/'docs/artifacts'):
            for path in set(parent.rglob('demands.json'))|set(parent.rglob('batch*.json'))|set(parent.rglob('development_inputs.json')):
                data=read(path)
                if isinstance(data,dict): used.update(tuple(t[:200]) for t in data.get('base',[]))
        inputs=[]
        for ds,es,name in ((20270301,20270302,'development'),(20270303,20270304,'internal_validation')):
            path=OUT/f'{name}_inputs.json';write(path,runner.generate(ds,es,used));inputs.append(path)
        write(OUT/'input_manifest.json',[{'path':str(p),'sha256':runner.digest(p)} for p in inputs])
        def evaluate(label,library,random_group=False):
            for rel,value in hashes.items():
                if runner.digest(ROOT/rel)!=value: raise RuntimeError('Registered source changed')
            summary=runner.evaluate(label,library,inputs,random_group)
            batches=[]
            for lo in (0,4):
                rows=summary['fitness'];d=[]
                for seed in range(11,16):
                    for trace in range(lo,lo+4):
                        a=next(r for r in rows if r['seed']==seed and r['trajectory']==trace and r['group']=='happo')
                        b=next(r for r in rows if r['seed']==seed and r['trajectory']==trace and r['group']=='llm_library')
                        d.append([b['cost']-a['cost'],b['backlog']-a['backlog']])
                batches.append(np.mean(d,axis=0).tolist())
            item={'label':label,'library':str(library),'candidates':read(library)['candidates'],
                  'summary':summary,'split_mean_delta':batches,'eligible':all(b[1]<=0 for b in batches),
                  'length':sum(len(r['when'])+len(r['delta']) for c in read(library)['candidates'] for r in c['rules'])}
            archive.append(item);write(OUT/'archive.json',archive);return item
        seeds=[ROOT/'docs/artifacts/operator_discovery_v1/repaired_library.json',ROOT/'results/llm_current_v2/round2_library.json',ROOT/'results/llm_current_v2/round6_library.json']
        for index,path in enumerate(seeds):
            fp=fingerprint(read(path),states)
            if fp in seen: continue
            seen.add(fp);evaluate(f'initial{index}',path,index==0)
        system=runner.SYSTEM+'''\nOFFLINE current report environment: each3 completed external demands become a block mean repeated3 times, available next decision. recent/baseline/growth use only these delivered values; agent0 incoming is last delivered reconstructed value, upstream incoming is previous downstream order. Current local inventory/backlog/pipeline/arrival and HAPPO proposal are globally observed. Rules have no other-node feature names. Notification arrives after two completed event periods; no end time or multiplier available online. Frozen five models,6 forecast paths (3search+3review),20period horizon, first5 corrected, reselect every5,1percent cost improvement and no predicted backlog increase required. You design3 diverse bounded rules; do not hardcode dates/seeds, cannot add features. True is valid, lowercase true is not. DSL only. Numerical guards must cover zero demand. Reflections use completed development cases only. When producing a library return JSON {candidates:[3 candidates]}; each candidate has explanation and1..4 when/delta rules. Do not just rephrase parents; change actual bounded integer actions in substantive state regions.'''
        def request(context,kind):
            body={'model':os.environ.get('DEEPSEEK_MODEL','deepseek-flash'),'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(context)}],
                  'response_format':{'type':'json_object'},'thinking':{'type':'disabled'},'temperature':.5,'max_tokens':4000}
            record={'kind':kind,'request':body,'status':'started'};calls.append(record);write(OUT/'calls.json',calls)
            write(OUT/'progress.json',{'status':'requesting','kind':kind,'requests':len(calls),'pid':os.getpid()});start=time.perf_counter()
            try:
                req=urllib.request.Request('https://api.deepseek.com/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=90) as response: result=json.load(response)
                record['response']=result;record['usage']=result.get('usage')
                choice=result['choices'][0]
                if choice['finish_reason']!='stop': raise ValueError('Incomplete output')
                content=json.loads(choice['message']['content']);record['status']='received';return content,record
            except urllib.error.HTTPError as exc:
                record['status']='failed';record['failure']='HTTP_'+str(exc.code)
                if exc.code in (401,402,403): raise RuntimeError('API authentication/balance/permission failure') from None
                return None,record
            except Exception as exc:
                record['status']='failed';record['failure']=str(exc)[:400];return None,record
            finally:
                record['seconds']=time.perf_counter()-start;write(OUT/'calls.json',calls)
        def ranking(item):
            # Length only breaks cost ties at a fixed1e-9 resolution.
            return (not item['eligible'],round(item['summary']['mean_delta'][0],9),item['length'])
        for generation in range(1,4):
            parents=sorted(archive,key=ranking)
            elite=parents[(generation-1)%min(2,len(parents))];other=parents[-1] if len(parents)>1 else elite
            context={'generation':generation,'elite':elite,'different_parent':other,'memory':memory[-3:],
                     'task':'Compare mechanisms and failures across five frozen models and development/internal validation; return JSON reflection string and memory string. No candidates yet.'}
            reflection=None
            for attempt in range(3):
                value,record=request(context,'reflection')
                if value and isinstance(value.get('reflection'),str): reflection=value;record['status']='valid';break
                record['status']='failed';record['failure']='Invalid reflection JSON';write(OUT/'calls.json',calls)
            if reflection is None: raise RuntimeError('Reflection unavailable after3 attempts')
            memory.append(reflection);write(OUT/'reflections.json',memory)
            for operation in ('biased_crossover','elite_mutation'):
                library=None
                for attempt in range(3):
                    context={'generation':generation,'operation':operation,'elite_candidates':elite['candidates'],
                             'different_parent_candidates':other['candidates'],'reflection':reflection,'prior_memory':memory[-3:],
                             'last_failure':calls[-1].get('failure'),
                             'instruction':'Crossover: retain sound elite principles, integrate a distinct useful mechanism from other parent. Mutation: change failure-region behavior while preserving successful behavior. Return exactly3 candidates. Improve both development and internal validation, use no tests.'}
                    value,record=request(context,operation)
                    if value:
                        try:
                            fp=fingerprint(value,states)
                            if fp in seen: raise ValueError('Behavior duplicate on registered bounded-action probes; substantive change required')
                            seen.add(fp);library=OUT/f'generation{generation}_{operation}.json';write(library,value);record['status']='valid'
                        except Exception as exc:
                            record['status']='failed';record['failure']=str(exc)[:400]
                    write(OUT/'calls.json',calls)
                    if library: break
                if library: evaluate(f'generation{generation}_{operation}',library)
                else: write(OUT/f'generation{generation}_{operation}_skipped.json',{'failure':'Three failed/duplicate candidates; all requests preserved'})
            write(OUT/'generation_progress.json',{'generation':generation,'elite_labels':[p['label'] for p in sorted(archive,key=ranking)[:2]],'evaluated_libraries':len(archive)})
            print('GENERATION_COMPLETED',generation,'libraries',len(archive),flush=True)
        winner=sorted([a for a in archive if a['eligible']],key=ranking)[0] if any(a['eligible'] for a in archive) else archive[0]
        frozen=OUT/'frozen_library.json';shutil.copy2(winner['library'],frozen)
        write(OUT/'frozen_manifest.json',{'source':winner['library'],'library_sha256':runner.digest(frozen),'selection':winner,'tests_not_generated_yet':True})
        directory=OUT/'test_inputs';directory.mkdir();tests=[]
        for n in range(1,6):
            path=directory/f'batch{n}.json';write(path,runner.generate(20270499+2*n,20270500+2*n,used));tests.append(path)
        write(directory/'manifest.json',{'inputs':[{'path':str(p),'sha256':runner.digest(p)} for p in tests],'frozen_library_sha256':runner.digest(frozen)})
        new=runner.evaluate('test_new',frozen,tests,True);old=runner.evaluate('test_old',seeds[0],tests)
        sys.path.insert(0,str(ROOT/'experiments/formal_evaluation'))
        from analyze_multi import compare
        def matrix(summary,g):
            return np.array([[next([r['cost'],r['backlog']] for r in summary['fitness'] if r['seed']==seed and r['trajectory']==trace and r['group']==g) for trace in range(20)] for seed in range(11,16)])
        a=matrix(new,'happo');assert np.array_equal(a,matrix(old,'happo'))
        summary={'vs_happo':compare(a,matrix(new,'llm_library')),'vs_old':compare(matrix(old,'llm_library'),matrix(new,'llm_library')),
                 'vs_random':compare(matrix(new,'random_screen'),matrix(new,'llm_library')),'api_requests':len(calls),
                 'api_failures':sum(r['status']=='failed' for r in calls),'usage':[r.get('usage') for r in calls],
                 'test_episodes':1000,'duplicate_happo_audit_episodes':200,'all_seeds_retained':True,
                 'limits':'Additional comparisons descriptive; vs_v2 discovery not budget matched. Synthetic behavioral deduplication does not prove equivalence in all states.'}
        write(OUT/'test_summary.json',summary);write(OUT/'completed.json',{'status':'completed','winner':winner['label'],'summary':summary})
        write(OUT/'progress.json',{'status':'completed','pid':os.getpid()});print('REFLECTIVE_EVOLUTION_COMPLETED',flush=True)
    except Exception as exc:
        write(OUT/'failed.json',{'failure':str(exc),'original_outputs_preserved':True});raise


if __name__=='__main__': main()
