"""Freeze methods/inputs/budget, then dispatch the sole paired API driver."""
import argparse
import math
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
import runner as r

ROOT,OUT,HERE=r.ROOT,r.OUT,r.HERE
read,write,sha=r.read,r.write,r.sha
SPEC=ROOT/'docs/superpowers/specs/2026-10-17-poisson-full-mechanism-design.md'
PLAN=ROOT/'docs/superpowers/plans/2026-10-17-poisson-full-mechanism.md'

def prepare():
    import numpy as np
    assert not OUT.exists()
    r.ref.verify()
    assert read(ROOT/'results/poisson_baseline_comparison/v1/independent_audit.json')['passed']
    OUT.mkdir(parents=True)
    files={ROOT/e['path'] for e in r.ref.read(r.ref.OUT/'registration.json')['files']}
    files.update(r.dependency_files())
    files.update(ROOT/p for p in r.core.source_hashes())
    files.update([SPEC,PLAN,*HERE.glob('*.py'),r.ref.OUT/'independent_audit.json',r.ref.OUT/'holdout_inputs.json'])
    from common import sources
    files.update(sources())
    # Cached model files bound by SHA, but large safetensors will not be archived.
    model=r.predictor.base.base.MODEL
    files.update(p for p in model.rglob('*') if p.is_file())
    hashes={str(p.relative_to(ROOT)) if ROOT in p.parents else str(p):sha(p) for p in sorted(files)}
    # Methods are frozen before the first background path generation.
    write(OUT/'method_freeze.json',dict(files=hashes,created=time.time(),api_http_cap=480,api_semantic_cap=240))
    seen=set()
    original=read(r.TRAIN/'inputs.json')
    for split in ('validation','baseline_development'):seen.update(r.ref.trace_hash(p) for p in original[split])
    for p in (r.TRAIN/'runs').glob('*/training_demands.jsonl'):
        with p.open(encoding='utf-8') as f:
            for line in f:seen.add(r.ref.trace_hash(__import__('json').loads(line)))
    seen.update(r.ref.trace_hash(p) for p in read(r.ref.OUT/'holdout_inputs.json')['paths'])
    historical=len(seen);base=[];attempts=[]
    for seed in range(20275101,20275151):
        path=np.random.default_rng(seed).poisson(10,200).tolist();h=r.ref.trace_hash(path);collision=h in seen
        attempts.append(dict(seed=seed,collision=collision,sha256=h))
        if collision:continue
        seen.add(h);base.append(path)
        if len(base)==3:break
    assert len(base)==3
    definitions=[('single_surge',[(70,90,1.5)]),('sustained_surge',[(60,110,1.25)]),('double_surge',[(65,85,1.5),(105,125,1.5)])]
    shock=[];events=[]
    for path,(kind,intervals) in zip(base,definitions):
        changed=path.copy()
        for a,b,factor in intervals:
            for t in range(a,b):changed[t]=math.ceil(factor*path[t])
        shock.append(changed);events.append(dict(type=kind,start_index=intervals[0][0],intervals=intervals,
              zero_actual_shock=changed==path,physical_demand_cap=None))
    write(OUT/'inputs.json',dict(base=base,shock=shock,events=events,attempts=attempts,historical_unique=historical,
          source='fresh independent Poisson10',created_after_method_freeze=True,posthoc_development=False))
    for p in (OUT/'method_freeze.json',OUT/'inputs.json'):hashes[p.relative_to(ROOT).as_posix()]=sha(p)
    # Abs paths retained for cached weights; verifier handles Path joining absolute values.
    write(OUT/'registration.json',dict(files=hashes,jobs=[dict(lead=l,seed=s) for l in (2,4) for s in range(11,16)],
         episodes=120,rows=72000,http_cap=480,semantic_cap=240,automatic_retry=False,model='deepseek-flash',
         h=[1,1,1],b=[1,0,0],large_cached_model_weights_public_sha_only=True))
    for lead in (2,4):
        p=OUT/f'SYSTEM_L{lead}.txt';p.write_text(r.system(lead),encoding='utf-8',newline='\n')
    print('PREPARED',len(hashes),flush=True)

def preflight():
    r.verify()
    for lead in (2,4):
        with (OUT/f'fixture_L{lead}.log').open('x',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-u',str(HERE/'runner.py'),'--lead',str(lead),'--seed','11','--fixture'],
                           cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    write(OUT/'preflight.json',dict(passed=True,fixture_episodes=8,fixture_rows=4800,http=0,real_sundial=True,synthetic_llm=True))
    paths=[ROOT/p for p in read(OUT/'registration.json')['files'] if ROOT in (ROOT/p).parents]
    paths.extend(p for p in OUT.rglob('*') if p.is_file())
    r.ref.archive(ROOT/'docs/artifacts/poisson_full_mechanism_preregistration',paths)
    print('PREFLIGHT_PASSED',flush=True)

def run():
    import winreg
    r.verify()
    assert read(OUT/'publication.json')['verified'] and read(OUT/'preflight.json')['passed']
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as reg:key=winreg.QueryValueEx(reg,'DEEPSEEK_API_KEY')[0]
    assert key
    os.environ['DEEPSEEK_API_KEY']=key;os.environ['DEEPSEEK_MODEL']='deepseek-flash'
    with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
    write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time()))
    completed=[];episodes=[];http=semantic=0
    try:
        for job in read(OUT/'registration.json')['jobs']:
            r.verify();label=f"L{job['lead']}_seed{job['seed']}"
            write(OUT/'progress.json',dict(status='running',current=label,completed=completed,total=10,http=http,semantic=semantic))
            with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:
                child=subprocess.Popen([sys.executable,'-u',str(HERE/'runner.py'),'--lead',str(job['lead']),'--seed',str(job['seed'])],
                                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                write(OUT/'active.json',dict(job=label,pid=child.pid,started=time.time()))
                code=child.wait()
            folder=OUT/'runs'/label
            calls=read(folder/'calls.json') if (folder/'calls.json').exists() else []
            http+=len(calls);semantic+=sum(c['attempt']==1 for c in calls)
            assert http<=480 and semantic<=240
            assert code==0,f'{label} failed; outputs retained, no automatic retry'
            assert read(folder/'independent_audit.json')['passed']
            completed.append(label);episodes.extend(read(folder/'episodes.json'));r.verify()
        assert len(episodes)==120
        by_lead={}
        for lead in (2,4):
            by_type={}
            for trace,event in enumerate(read(OUT/'inputs.json')['events']):
                means={m:sum(e['cost'] for e in episodes if e['lead']==lead and e['trace']==trace and e['scenario']=='shock' and e['group']==m)/5 for m in ('happo','full_sundial')}
                by_type[event['type']]=dict(**means,difference=means['full_sundial']-means['happo'])
            by_lead[str(lead)]=dict(by_type=by_type,by_seed={str(seed):{m:sum(e['cost'] for e in episodes if e['lead']==lead and e['seed']==seed and e['scenario']=='shock' and e['group']==m)/3 for m in ('happo','full_sundial')} for seed in range(11,16)})
        write(OUT/'summary.json',dict(by_lead=by_lead,http=http,semantic=semantic,episodes=120,independent_paths=3,
              inferential_claim='small paired comparison, no broad confirmation',all_seeds_preserved=True))
        write(OUT/'completed.json',dict(jobs=10,episodes=120,rows=72000,http=http,semantic=semantic))
        write(OUT/'progress.json',dict(status='completed',completed=completed,http=http,semantic=semantic))
        r.ref.archive(ROOT/'docs/artifacts/poisson_full_mechanism_completed',[p for p in OUT.rglob('*') if p.is_file()]+list(HERE.glob('*.py'))+[SPEC,PLAN])
    except BaseException:
        write(OUT/'failed.json',dict(completed=completed,http=http,semantic=semantic,traceback=traceback.format_exc(),preserved=True))
        write(OUT/'progress.json',dict(status='failed',completed=completed,http=http,semantic=semantic))
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','preflight','run'));globals()[p.parse_args().action]()
