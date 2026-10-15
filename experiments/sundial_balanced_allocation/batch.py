"""Exclusive all-seed all-type allocation development, immutable registration."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
OUT=ROOT/'results/sundial_balanced_allocation/v1'
INPUT=ROOT/'results/sundial_closed_loop_development/development_v2/inputs/stationary.json'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def register():
 import runner
 auditor=runner.module('balanced_local_auditor',HERE/'audit.py')
 files={str(ROOT/p):v for p,v in runner.core.source_hashes().items()}
 for seed in range(11,16):
  c=runner.core.contracts(INPUT,runner.core.LIBRARY,runner.core.training(seed));files.update(c['model_files']);files.update(c['happo_contract']['hashes'])
  for trace in range(4):
   directory=auditor.reference(seed,trace);assert read(directory/'independent_audit.json')['status']=='passed'
   for p in directory.rglob('*'):
    if p.is_file():files[str(p)]=sha(p)
 for p in (INPUT,runner.predictor.ADAPTER):files[str(p)]=sha(p)
 assert not OUT.exists();OUT.mkdir(parents=True)
 write(OUT/'registration.json',dict(files=files,tasks=[dict(seed=s,trace=t) for s in range(11,16) for t in range(4)],episodes=40,rows=24000,api_budget=0,created=time.time(),allocation_variant='balanced_rotating_remainder',development_only=True))
def verify():
 r=read(OUT/'registration.json')
 for p,v in r['files'].items():assert sha(Path(p))==v,p
 return r
def run():
 import runner
 auditor=runner.module('balanced_local_auditor',HERE/'audit.py')
 registration=verify()
 with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time()));completed=[];summary=[]
 try:
  for task in registration['tasks']:
   seed,trace=task['seed'],task['trace'];label=f'seed{seed}_trace{trace}';verify();write(OUT/'progress.json',dict(status='running',task=label,completed=completed,total_tasks=20))
   cmd=[sys.executable,'-u',str(HERE/'runner.py'),'--seed',str(seed),'--trace',str(trace),'--run-name',label,'--input-file',str(INPUT),'--training-directory',str(runner.core.training(seed)),'--output-root',str(OUT/'runs'),'--phase','development']
   with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:p=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
   assert p.returncode==0,f'{label} failed; preserve outputs'
   summary.extend(auditor.audit(runner,OUT/'runs'/label,seed,trace,read(INPUT)));completed.append(task);verify();write(OUT/'summary.json',summary)
  write(OUT/'completed.json',dict(episodes=40,rows=24000,api=0,tasks=completed));write(OUT/'progress.json',dict(status='completed',completed=completed,total_tasks=20))
 except Exception as e:write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),completed=completed,preserved=True));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run'));a=p.parse_args();{'register':register,'run':run}[a.action]()
