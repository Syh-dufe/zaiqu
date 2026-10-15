"""Pure frozen HAPPO supplement on the exact cached Sundial demand paths."""
import argparse,csv,gzip,hashlib,importlib.util,json,os,socket,sys,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/sundial_pure_happo/cached_paths_v2'
INPUT=ROOT/'results/sundial_closed_loop_development/development_v2/inputs/stationary.json'
PLAN=ROOT/'docs/superpowers/plans/2026-10-15-cached-path-pure-happo.md'
spec=importlib.util.spec_from_file_location('pure_cached_core',ROOT/'experiments/submission_required/run_online.py')
core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)
core.METHODS=('happo',)
original_contracts=core.contracts
def contracts(*a,**kw):
    kw['require_key']=False
    v=original_contracts(*a,**kw);v.update(development_only=True,independent_confirmation=False,pure_happo=True,api_budget=0)
    return v
core.contracts=contracts
read,write,sha=core.read,core.write,core.digest

def reference(seed,new=False):
    return ROOT/(f'results/sundial_cached_api/development_v1/runs/seed{seed}_four_types' if new else f'results/sundial_closed_loop_development/development_v2/runs/batch01_seed{seed}')

def register():
    assert not OUT.exists()
    files={str(ROOT/p):h for p,h in core.source_hashes().items()}
    for p in (Path(__file__),PLAN,INPUT):files[str(p)]=sha(p)
    cs={}
    for seed in (11,12):
        c=contracts(INPUT,core.LIBRARY,core.training(seed));cs[str(seed)]=c
        files.update(c['happo_contract']['hashes']);files.update(c['ippo_contract']['hashes'])
        for new in (False,True):
            ref=reference(seed,new);assert read(ref/'audit.json')['status']=='passed'
            p=read(ref/'protocol.json');assert p['input_sha256']==sha(INPUT) and p['expected_parameter_sha256']==c['expected_parameter_sha256']
            for f in ref.rglob('*'):
                if f.is_file():files[str(f)]=sha(f)
    OUT.mkdir(parents=True);write(OUT/'registration.json',dict(files=files,contracts=cs,episodes=16,rows=9600,api=0))
    print('REGISTERED',flush=True)

def verify():
    reg=read(OUT/'registration.json')
    for p,h in reg['files'].items():assert sha(Path(p))==h,p
    return reg

def load_rows(path):
    with path.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

def audit(seed,d):
    rows=load_rows(d/'periods.csv');episodes=read(d/'episodes.json');data=read(INPUT)
    assert len(rows)==4800 and len(episodes)==8
    ids={(r['scenario'],int(r['trace']),int(r['period']),int(r['node'])) for r in rows};assert len(ids)==4800
    for r in rows:
        assert r['group']=='happo' and int(r['actual_order'])==int(r['policy_order']) and 0<=int(r['actual_order'])<=20
        assert float(r['cost'])==int(r['inventory'])+int(r['backlog'])
        assert int(r['demand'])==data[r['scenario']][int(r['trace'])][int(r['period'])-1]
    for e in episodes:
        local=[r for r in rows if r['scenario']==e['scenario'] and int(r['trace'])==e['trace']]
        assert len(local)==600 and abs(sum(float(r['cost']) for r in local)/600-e['cost'])<1e-10
        assert e['episode_http']==e['generation_events']==0
    model=read(d/'completed.json')['parameter_checks'];expected=read(d/'protocol.json')['expected_parameter_sha256']
    assert model['happo']['before']==model['happo']['after']==expected
    mapping={(r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in rows}
    for new in (False,True):
        for r in load_rows(reference(seed,new)/'periods.csv'):
            if r['group']!=('adapted_sundial' if new else 'original_merton'):continue
            period=int(r['period']);trace=int(r['trace'])
            if r['scenario']=='base' or period<data['events'][trace]['start_index']+3:
                other=mapping[(r['scenario'],trace,period,int(r['node']))]
                assert all(float(r[k])==float(other[k]) for k in ('cost','actual_order','inventory','backlog','demand'))
    assert read(d/'calls.json')==[] and read(d/'scores.json')==[]
    write(d/'audit.json',dict(status='passed',episodes=8,rows=4800,api=0,raw_cost_recomputed=True,orders_equal_actor=True,models_frozen=True,paired_prefixes=True))

def run():
    reg=verify();lock=OUT/'started.lock'
    with lock.open('x') as f:f.write(str(os.getpid()))
    class NoClient:
        def __init__(self,out,*a):self.records=[];self.episode_http=0;write(out/'calls.json',[])
        def reset_episode(self):self.episode_http=0
        def generate(self,*a,**kw):raise RuntimeError('Pure HAPPO must not request candidates')
    core.Client=NoClient
    import torch
    def forbidden(*a,**kw):raise RuntimeError('Network disabled for pure HAPPO')
    socket.socket=forbidden;socket.create_connection=forbidden
    allrows=[]
    for seed in (11,12):
        verify();write(OUT/'progress.json',dict(status='running',seed=seed,api=0))
        d=OUT/f'seed{seed}';d.mkdir();c=contracts(INPUT,core.LIBRARY,core.training(seed));assert c==reg['contracts'][str(seed)]
        write(d/'protocol.json',c);write(d/'demands.json',read(INPUT))
        opts=argparse.Namespace(input_file=INPUT,operator_library=core.LIBRARY,training_directory=core.training(seed),phase='development')
        core.evaluate(opts,d,c,read(INPUT));audit(seed,d);verify()
        for e in read(d/'episodes.json'):
            if e['scenario']!='shock':continue
            trace=e['trace'];values={}
            for new in (False,True):
                group='adapted_sundial' if new else 'original_merton'
                values[group]=next(x['cost'] for x in read(reference(seed,new)/'episodes.json') if x['group']==group and x['scenario']=='shock' and x['trace']==trace)
            allrows.append(dict(seed=seed,trace=trace,type=read(INPUT)['events'][trace]['type'],happo=e['cost'],**values))
    write(OUT/'comparison.json',allrows);write(OUT/'completed.json',dict(episodes=16,rows=9600,api=0,status='passed'))
    write(OUT/'progress.json',dict(status='completed',seeds=[11,12],api=0));print('PURE_HAPPO_COMPLETED',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run'));a=p.parse_args()
    try:register() if a.action=='register' else run()
    except Exception as e:
        if OUT.exists():write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),preserved=True))
        raise
