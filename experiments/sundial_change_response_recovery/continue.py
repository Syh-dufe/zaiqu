"""Reuse both completed zero runs; explicit-file audit fix, immutable old source."""
import argparse,concurrent.futures,gzip,hashlib,importlib.util,inspect,json,os,subprocess,sys,time,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
OLD=ROOT/'results/sundial_change_response/v1';OUT=ROOT/'results/sundial_change_response_recovery/v1'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
runner=module('recovery_original_response_runner',ROOT/'experiments/sundial_change_response/runner.py')
base=module('recovery_original_response_batch',ROOT/'experiments/sundial_change_response/batch.py')
original=module('recovery_original_response_audit',ROOT/'experiments/sundial_change_response/audit.py')
text=inspect.getsource(original.audit);assert text.count("v['horizon']")==1
text=text.replace("v['horizon']","min(20,201-s['decision_period'])")
namespace=dict(original.__dict__);exec(compile(text,str(Path(__file__)),'exec'),namespace)
read,write,sha=base.read,base.write,base.sha
def audit(directory,seed,candidate):
 for s in read(directory/'scores.json'):
  h=min(20,201-s['decision_period']);assert all(len(path)==h for paths in s['forecasts'] for path in paths)
 return namespace['audit'](runner,directory,seed,candidate,read(OLD/'calibration_inputs.json'))
def register():
 base.verify();assert not OUT.exists();OUT.mkdir(parents=True);summary=[];reused={}
 for seed in (11,14):
  directory=OLD/'runs'/f'seed{seed}_zero';summary.extend(audit(directory,seed,'zero'))
  for p in directory.rglob('*'):
   if p.is_file():reused[str(p)]=sha(p)
 write(OUT/'reused_summary.json',summary)
 files=dict(read(OLD/'registration.json')['files']);files.update(reused)
 for p in [Path(__file__),ROOT/'docs/superpowers/plans/2026-10-15-sundial-response-audit-recovery.md',OLD/'registration.json',OLD/'failed.json',OLD/'progress.json',OUT/'reused_summary.json']:files[str(p)]=sha(p)
 write(OUT/'registration.json',dict(files=files,reused_tasks=[dict(seed=s,candidate='zero') for s in (11,14)],remaining_tasks=[t for t in read(OLD/'registration.json')['tasks'] if t['candidate']!='zero'],max_processes=2,api=0,original_failure_preserved=True,actual_runner_unchanged=True))
 package=ROOT/'docs/artifacts/sundial_response_audit_recovery_v1';assert not package.exists();package.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 entries={};paths=[Path(__file__),ROOT/'docs/superpowers/plans/2026-10-15-sundial-response-audit-recovery.md',OLD/'failed.json',OLD/'progress.json',OUT/'registration.json',OUT/'reused_summary.json']+[Path(p) for p in reused]
 for i,p in enumerate(paths):
  raw=p.read_bytes();assert key not in raw;dest=package/f'{i:03d}.gz';dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=sha(p),gzip_sha256=sha(dest))
 (package/'manifest.json').write_bytes(json.dumps(dict(files=entries,lossless=True,credential_absent=True,api=0),indent=2).encode());print('RESPONSE_RECOVERY_REGISTERED',len(entries),flush=True)
def verify():
 r=read(OUT/'registration.json')
 for p,s in r['files'].items():assert sha(Path(p))==s,p
 return r
def run():
 registration=verify()
 with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time()));summary=read(OUT/'reused_summary.json');completed=registration['reused_tasks'].copy();pending=iter(registration['remaining_tasks']);active={}
 def progress():write(OUT/'progress.json',dict(status='running',completed=completed,active=[v[1] for v in active.values()],total_tasks=10,reused_tasks=2))
 def start(executor,task):
  verify();seed,candidate=task['seed'],task['candidate'];label=f'seed{seed}_{candidate}'
  def execute():
   cmd=[sys.executable,'-u',str(ROOT/'experiments/sundial_change_response/runner.py'),'--seed',str(seed),'--candidate',candidate,'--run-name',label,'--input-file',str(OLD/'calibration_inputs.json'),'--training-directory',str(runner.core.training(seed)),'--output-root',str(OLD/'runs'),'--phase','development']
   with (OLD/f'{label}.log').open('x',encoding='utf-8') as log:return subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
  active[executor.submit(execute)]=(task,label)
 try:
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
   for _ in range(2):start(executor,next(pending))
   progress()
   while active:
    finished,_=concurrent.futures.wait(active,return_when=concurrent.futures.FIRST_COMPLETED)
    for future in finished:
     task,label=active.pop(future);assert future.result()==0,f'{label} program failure; preserve'
     summary.extend(audit(OLD/'runs'/label,task['seed'],task['candidate']));completed.append(task);verify();write(OUT/'summary.json',summary)
    for _ in range(len(finished)):
     task=next(pending,None)
     if task is not None:start(executor,task)
    progress()
  order=read(OLD/'registration.json')['candidates'];means={c:sum(x['cost'] for x in summary if x['candidate']==c and x['scenario']=='shock')/8 for c in order};winner=min(order,key=lambda c:means[c]);gate=winner!='zero' and means[winner]<=.99*means['zero']
  selection=dict(means=means,winner=winner,gate_passed=gate,cost_reduction_percent=100*(1-means[winner]/means['zero']),validation_not_run=True)
  write(OUT/'selection.json',selection);write(OUT/'completed.json',dict(episodes=80,rows=48000,api=0,tasks=completed,reused_tasks=2));write(OUT/'progress.json',dict(status='completed',completed=completed,total_tasks=10,gate_passed=gate))
 except Exception as e:write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),completed=completed,preserved=True,no_blind_restart=True));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run'));a=p.parse_args();{'register':register,'run':run}[a.action]()
