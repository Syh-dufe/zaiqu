"""Exact reply reuse and manual continuation after registered network failure."""
import argparse
import copy
import csv
import gzip
import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
OLD=ROOT/'results/poisson_full_mechanism/v1'
OUT=ROOT/'results/poisson_full_mechanism/network_recovery_v1'
PLAN=ROOT/'docs/superpowers/plans/2026-10-17-poisson-network-recovery.md'
sys.path.insert(0,str(ROOT/'experiments/poisson_full_mechanism'))
import runner as r
read,write,sha=r.read,r.write,r.sha
OLD_VERIFY=r.verify
OLD_CLIENT=r.ActualClient
OLD_CALLS=OLD/'runs/L2_seed11/calls.json'

def verify():
    previous=r.OUT;r.OUT=OLD
    try:OLD_VERIFY()
    finally:r.OUT=previous
    reg=read(OUT/'registration.json')
    for p,h in reg['files'].items():assert sha(ROOT/p)==h,p
    return reg

def normalized(context,count):
    context=copy.deepcopy(context)
    if 'forecast_protocol' in context:
        context['forecast_protocol']='6 frozen response-Sundial synthetic paths bounded0..20; search3/review3,horizon20; correction first5. Physical Poisson demand may exceed20.'
    return dict(context,candidate_count=count)

def identity_key(identity,stage):
    return tuple(identity[k] for k in ('lead','seed','group','scenario','trace','event'))+(stage,)

def setup(lead,seed,offline=False):
    r.OUT=OUT/ 'fixtures/offline_replay' if offline else OUT
    r.verify=verify
    prior=read(OLD_CALLS)
    cache={}
    if (lead,seed)==(2,11):
        for c in prior:cache.setdefault(identity_key(c,c['stage']),[]).append(c)
        cache={k:v for k,v in cache.items() if any(c['status']=='valid' for c in v)}
        assert len(cache)==14
    class RecoveryClient(OLD_CLIENT):
        def __init__(self,output,system,model):
            self.reused=set();self.offline=offline
            if offline:
                self.output=output;self.system=system;self.model=model;self.key='noncredential_offline_replay';self.records=[];self.episode_http=0;self.save()
            else:super().__init__(output,system,model)
            protocol=read(output/'protocol.json')
            protocol.update(recovery=True,offline_replay=offline,synthetic_after_failure=offline,
                            original_failure_preserved=True,historical_physical_http=19)
            write(output/'protocol.json',protocol)
        def save(self):
            super().save()
            if offline:return
            physical=[c for c in self.records if c.get('new_http',True)]
            budget=read(OUT/'budget_state.json')
            assert budget['http']+len(physical)<=480
            assert budget['semantic']+sum(c['attempt']==1 for c in physical)<=241
            if (lead,seed)==(2,11):
                for trace in range(3):
                    historical=sum(c['trace']==trace for c in prior)
                    assert historical+sum(c['trace']==trace for c in physical)<=16
        def generate(self,context,count,identity,stage):
            key=identity_key(identity,stage)
            if key in cache:
                assert key not in self.reused
                self.reused.add(key)
                rows=cache[key];expected=normalized(context,count)
                assert all(c['request']['messages'][0]['content']==self.system and
                           json.loads(c['request']['messages'][1]['content'])==expected for c in rows), 'Exact cached request differs'
                assert self.episode_http+len(rows)<=16
                for c in rows:
                    value=copy.deepcopy(c)
                    value.update(new_http=False,reused_from=OLD_CALLS.relative_to(ROOT).as_posix(),reused_source_sha256=sha(OLD_CALLS))
                    self.records.append(value)
                self.episode_http+=len(rows);self.save()
                valid=next(c for c in rows if c['status']=='valid')
                assert len(valid['candidates'])==count
                return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=value,compiled=r.core.compile_rule(value)) for i,value in enumerate(valid['candidates'])]
            if offline:
                self.episode_http+=1;assert self.episode_http<=16
                values=[{'explanation':'Synthetic continuation fixture, not performance','rules':[{'when':'True','delta':'0'}]} for _ in range(count)]
                self.records.append(dict(**identity,stage=stage,attempt=1,status='valid',new_http=False,offline_generated=True,
                    candidates=values,request=dict(messages=[dict(role='system',content=self.system),dict(role='user',content=json.dumps(normalized(context,count),ensure_ascii=False))])))
                self.save()
                return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=value,compiled=r.core.compile_rule(value)) for i,value in enumerate(values)]
            return super().generate(context,count,identity,stage)
    r.ActualClient=RecoveryClient

def worker(lead,seed,offline=False):
    verify();setup(lead,seed,offline)
    r.execute(lead,seed,fixture=False)
    folder=r.OUT/'runs'/f'L{lead}_seed{seed}'
    calls=read(folder/'calls.json');physical=[c for c in calls if c.get('new_http',True)]
    write(folder/'recovery_accounting.json',dict(offline=offline,new_http=0 if offline else len(physical),
         new_semantic=0 if offline else sum(c['attempt']==1 for c in physical),logical_call_records=len(calls),
         reused_physical_records=sum('reused_from' in c for c in calls),historical_http_counted_once=19,
         no_performance_claim_from_fixture=offline))
    if offline:
        with gzip.open(OLD/'runs/L2_seed11/periods.csv.gz','rt',encoding='utf-8',newline='') as f:old_rows=list(csv.DictReader(f))
        with gzip.open(folder/'periods.csv.gz','rt',encoding='utf-8',newline='') as f:new_rows=list(csv.DictReader(f))
        assert new_rows[:len(old_rows)]==old_rows,'Original completed/partial raw period prefix differs'
        assert sum('reused_from' in c for c in calls)==18
        write(OUT/'replay_preflight.json',dict(passed=True,offline=True,new_http=0,reused_semantic=14,
             reused_physical_records=18,all_old_period_rows_exact=True,old_period_rows=len(old_rows),
             completed_episodes=12,synthetic_after_failure=True,performance_result=False))
    verify()

def prepare():
    assert not OUT.exists()
    assert read(OLD/'failed.json')['http']==19
    assert read(OLD/'failed.json')['semantic']==15
    assert read(OLD_CALLS)[-1]['failure_kind']=='transport'
    OLD_VERIFY();OUT.mkdir(parents=True)
    paths={ROOT/p for p in read(OLD/'registration.json')['files']}
    paths.update(p for p in OLD.rglob('*') if p.is_file())
    paths.update([*HERE.glob('*.py'),PLAN])
    (OUT/'inputs.json').write_bytes((OLD/'inputs.json').read_bytes())
    paths.add(OUT/'inputs.json')
    write(OUT/'registration.json',dict(files={str(p.relative_to(ROOT)) if ROOT in p.parents else str(p):sha(p) for p in paths},
          jobs=read(OLD/'registration.json')['jobs'],historical_http=19,historical_semantic=15,http_cap=480,semantic_cap=241,
          manual_network_resume=True,automatic_retry=False,model_and_inputs_unchanged=True))
    print('RECOVERY_PREPARED',flush=True)

def preflight():
    verify()
    with (OUT/'replay_preflight.log').open('x',encoding='utf-8') as log:
        subprocess.run([sys.executable,'-u',str(__file__),'worker','--lead','2','--seed','11','--offline'],cwd=ROOT,
                       stdout=log,stderr=subprocess.STDOUT,check=True)
    assert read(OUT/'replay_preflight.json')['passed']
    paths=[ROOT/p for p in read(OUT/'registration.json')['files'] if ROOT in (ROOT/p).parents]
    paths.extend(p for p in OUT.rglob('*') if p.is_file())
    r.ref.archive(ROOT/'docs/artifacts/poisson_network_recovery_preregistration',paths)
    print('RECOVERY_PREFLIGHT_PASSED',flush=True)

def run():
    import winreg
    verify();assert read(OUT/'publication.json')['verified'];assert read(OUT/'replay_preflight.json')['passed']
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as reg:key=winreg.QueryValueEx(reg,'DEEPSEEK_API_KEY')[0]
    assert key;os.environ['DEEPSEEK_API_KEY']=key
    with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
    write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time()))
    http,semantic=19,15;completed=[];episodes=[]
    try:
        for job in read(OUT/'registration.json')['jobs']:
            verify();label=f"L{job['lead']}_seed{job['seed']}"
            write(OUT/'progress.json',dict(status='running',completed=completed,current=label,total=10,http=http,semantic=semantic))
            write(OUT/'budget_state.json',dict(http=http,semantic=semantic))
            with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:
                child=subprocess.Popen([sys.executable,'-u',str(__file__),'worker','--lead',str(job['lead']),'--seed',str(job['seed'])],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                write(OUT/'active.json',dict(job=label,pid=child.pid,started=time.time()));code=child.wait()
            folder=OUT/'runs'/label
            calls=read(folder/'calls.json') if (folder/'calls.json').exists() else []
            physical=[c for c in calls if c.get('new_http',True)]
            http+=len(physical);semantic+=sum(c['attempt']==1 for c in physical)
            assert http<=480 and semantic<=241
            assert code==0,f'{label} failed; preserve all outputs, no automatic retry'
            assert read(folder/'independent_audit.json')['passed']
            episodes.extend(read(folder/'episodes.json'));completed.append(label)
        assert len(episodes)==120
        summary={}
        for lead in (2,4):
            summary[str(lead)]={}
            for trace,event in enumerate(read(OUT/'inputs.json')['events']):
                means={m:sum(e['cost'] for e in episodes if e['lead']==lead and e['trace']==trace and e['scenario']=='shock' and e['group']==m)/5 for m in ('happo','full_sundial')}
                summary[str(lead)][event['type']]=dict(**means,difference=means['full_sundial']-means['happo'])
        verify();write(OUT/'episodes.json',episodes);write(OUT/'summary.json',dict(by_lead=summary,http=http,semantic=semantic,all_seeds_retained=True,three_independent_paths_only=True))
        write(OUT/'completed.json',dict(jobs=10,episodes=120,rows=72000,http=http,semantic=semantic,historical_http=19,historical_semantic=15))
        write(OUT/'progress.json',dict(status='completed',completed=completed,http=http,semantic=semantic))
        r.ref.archive(ROOT/'docs/artifacts/poisson_network_recovery_completed',[p for p in OUT.rglob('*') if p.is_file()]+list(HERE.glob('*.py'))+[PLAN])
    except BaseException:
        write(OUT/'failed.json',dict(completed=completed,http=http,semantic=semantic,traceback=traceback.format_exc(),preserved=True))
        write(OUT/'progress.json',dict(status='failed',completed=completed,http=http,semantic=semantic));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','preflight','worker','run'))
    p.add_argument('--lead',type=int,choices=(2,4));p.add_argument('--seed',type=int,choices=range(11,16));p.add_argument('--offline',action='store_true')
    a=p.parse_args()
    if a.action=='worker':worker(a.lead,a.seed,a.offline)
    else:globals()[a.action]()
