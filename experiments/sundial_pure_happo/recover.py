"""Preserve seed11, handle absent unused scores, evaluate seed12 only."""
import argparse,inspect,os,socket
from pathlib import Path
import run as base
ROOT=base.ROOT;OUT=ROOT/'results/sundial_pure_happo/audit_recovery_v1'
def audited(seed,d):
    source=inspect.getsource(base.audit)
    marker="assert read(d/'calls.json')==[] and read(d/'scores.json')==[]"
    assert source.count(marker)==1
    source=source.replace(marker,"assert read(d/'calls.json')==[] and (not (d/'scores.json').exists() or read(d/'scores.json')==[])\n    assert read(d/'completed.json')['calls']==0 and read(d/'completed.json')['runtime_failures']==[]")
    ns=dict(base.__dict__);exec(compile(source,__file__,'exec'),ns);ns['audit'](seed,d)

def register():
    assert not OUT.exists();base.verify()
    assert base.read(base.OUT/'failed.json')['type']=='FileNotFoundError'
    files={}
    for p in [Path(__file__),ROOT/'docs/superpowers/plans/2026-10-15-pure-happo-audit-recovery.md']+list(base.OUT.rglob('*')):
        if p.is_file():files[str(p)]=base.sha(p)
    OUT.mkdir(parents=True);base.write(OUT/'registration.json',dict(files=files,reuse_seed11=True,remaining=[12],api=0))

def run():
    reg=base.read(OUT/'registration.json')
    for p,h in reg['files'].items():assert base.sha(Path(p))==h,p
    base.verify()
    with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
    # Audit writes in a new directory: the complete seed11 raw records stay bound.
    import shutil
    first=OUT/'seed11';shutil.copytree(base.OUT/'seed11',first);audited(11,first)
    class NoClient:
        def __init__(self,out,*a):self.records=[];self.episode_http=0;base.write(out/'calls.json',[])
        def reset_episode(self):self.episode_http=0
        def generate(self,*a,**kw):raise RuntimeError('No API in pure HAPPO')
    base.core.Client=NoClient
    import torch
    def forbidden(*a,**kw):raise RuntimeError('Network disabled')
    socket.socket=forbidden;socket.create_connection=forbidden
    d=OUT/'seed12';d.mkdir();c=base.contracts(base.INPUT,base.core.LIBRARY,base.core.training(12))
    assert c==base.read(base.OUT/'registration.json')['contracts']['12']
    base.write(d/'protocol.json',c);base.write(d/'demands.json',base.read(base.INPUT))
    opts=argparse.Namespace(input_file=base.INPUT,operator_library=base.core.LIBRARY,training_directory=base.core.training(12),phase='development')
    base.core.evaluate(opts,d,c,base.read(base.INPUT));audited(12,d);base.verify()
    comparison=[]
    for seed in (11,12):
        for e in base.read(OUT/f'seed{seed}/episodes.json'):
            if e['scenario']!='shock':continue
            values={}
            for new in (False,True):
                group='adapted_sundial' if new else 'original_merton'
                values[group]=next(x['cost'] for x in base.read(base.reference(seed,new)/'episodes.json') if x['group']==group and x['scenario']=='shock' and x['trace']==e['trace'])
            comparison.append(dict(seed=seed,trace=e['trace'],type=base.read(base.INPUT)['events'][e['trace']]['type'],happo=e['cost'],**values))
    for p,h in reg['files'].items():assert base.sha(Path(p))==h,p
    base.write(OUT/'comparison.json',comparison);base.write(OUT/'completed.json',dict(status='passed',episodes=16,rows=9600,api=0,reused_seed11=True))
    print('PURE_HAPPO_RECOVERY_COMPLETED',flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run'));a=p.parse_args()
    try:register() if a.action=='register' else run()
    except Exception as e:
        if OUT.exists():base.write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),preserved=True))
        raise
