"""New authorized subset batch; never resumes or overwrites the user-stopped batch."""
import argparse,gzip,hashlib,json,os,subprocess,sys,time,urllib.request
from pathlib import Path
import runner
ROOT=runner.ROOT;HERE=runner.HERE;core=runner.core
common=runner.module('focus_protected_common',ROOT/'experiments/submission_required/common.py');analysis=runner.module('focus_cost_analysis',HERE/'analyze.py');auditor=runner.module('focus_cost_auditor',HERE/'audit.py')
read,write,digest=common.read,common.write,common.digest
OUT=ROOT/'results/sundial_focus_completion/v1';OLD=ROOT/'results/sundial_closed_loop_development/development_v2';PACKAGE=ROOT/'docs/artifacts/sundial_focus_completion_v1_preregistration'

def balance():
 r=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY']})
 with urllib.request.urlopen(r,timeout=30) as response:value=json.loads(response.read())
 return value.get('is_available') is True

def register():
 assert not OUT.exists();assert read(OLD/'user_stopped.json')['status']=='stopped_by_user'
 fixture=ROOT/'results/sundial_focus_completion/no_api_reaudit_v2/preflight_passed.json';v=read(fixture);assert v['status']=='passed' and v['network_requests']==0 and v['exact_old_node_periods'] and v['exact_old_forecast_choices']
 oldf=read(OLD/'freeze.json')
 for p,s in oldf['source_sha256'].items():assert digest(ROOT/p)==s,p
 for p,s in oldf['dependencies'].items():assert digest(p)==s,p
 source=OLD/'inputs/stationary.json';core.validate_inputs(read(source))
 contracts={str(s):core.contracts(source,core.LIBRARY,core.training(s)) for s in range(11,16)}
 reuse={}
 for seed in (11,12):
  directory=OLD/f'runs/batch01_seed{seed}';assert read(directory/'audit.json')['status']=='passed'
  for p in directory.rglob('*'):
   if p.is_file():reuse[str(p)]=digest(p)
 OUT.mkdir(parents=True)
 write(OUT/'freeze.json',dict(source_sha256=core.source_hashes(),dependencies=oldf['dependencies'],contracts=contracts,reused_sha256=reuse,
 input_path=str(source),input_sha256=digest(source),fixture_sha256=digest(fixture),adapter_sha256=digest(runner.predictor.ADAPTER),system_sha256=hashlib.sha256(core.SYSTEM.encode()).hexdigest(),executable_sha256=digest(sys.executable),api_model='deepseek-flash',old_batch_stays_stopped=True))
 tasks=[dict(task=f'seed{s}_two_types',seed=s,max_http=64,max_semantic=32) for s in (13,14,15)]
 write(OUT/'manifest.json',dict(tasks=tasks,methods=runner.METHODS,selected_traces=runner.SELECTED,total_episodes=40,new_episodes=24,node_periods=24000,new_node_periods=14400,
 first_caps=[192,96],cumulative_caps=[384,192],freeze_sha256=digest(OUT/'freeze.json'),post_selected_development=True,historical_http_separate=273))
 print('FOCUS_REGISTERED_THREE_TASKS_24_NEW_EPISODES',flush=True)

def verify():
 m=read(OUT/'manifest.json');f=read(OUT/'freeze.json');assert digest(OUT/'freeze.json')==m['freeze_sha256'] and core.source_hashes()==f['source_sha256']
 assert digest(sys.executable)==f['executable_sha256'] and digest(runner.predictor.ADAPTER)==f['adapter_sha256'] and digest(f['input_path'])==f['input_sha256']
 assert read(OLD/'user_stopped.json')['status']=='stopped_by_user' and read(OLD/'progress.json')['status']=='stopped_by_user'
 for p,s in f['dependencies'].items():assert digest(p)==s,p
 for p,s in f['reused_sha256'].items():assert digest(p)==s,p
 for c in f['contracts'].values():
  for key in ('happo_contract','ippo_contract'):
   for p,s in c[key]['hashes'].items():assert digest(p)==s,p
 assert hashlib.sha256(core.SYSTEM.encode()).hexdigest()==f['system_sha256'];return m,f

def publish():
 m,f=verify();assert not PACKAGE.exists();PACKAGE.mkdir(parents=True)
 files=[ROOT/p for p in f['source_sha256']]+[OUT/'freeze.json',OUT/'manifest.json',Path(f['input_path'])]
 files += [p for p in (ROOT/'results/sundial_focus_completion/no_api_replay_v1').rglob('*') if p.is_file()]
 files += [p for p in (ROOT/'results/sundial_focus_completion/no_api_reaudit_v2').rglob('*') if p.is_file()]+[ROOT/'results/sundial_focus_preflight_v1.log']
 files += [runner.predictor.ADAPTER,OLD/'user_stopped.json']+[Path(p) for p in f['reused_sha256']]
 entries={};checks={};key=os.environ['DEEPSEEK_API_KEY'].encode()
 for i,p in enumerate(dict.fromkeys(files)):
  raw=p.read_bytes();assert key not in raw;dest=PACKAGE/'files'/f'{i:04d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  name=dest.relative_to(ROOT).as_posix();checks[name]=digest(dest);entries[name]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 write(PACKAGE/'manifest.json',dict(files=entries,lossless=True,credential_absent=True,checkpoint_local_only=True));checks[(PACKAGE/'manifest.json').relative_to(ROOT).as_posix()]=digest(PACKAGE/'manifest.json')
 write(OUT/'publication.json',dict(git_files=checks,freeze_sha256=digest(OUT/'freeze.json'),manifest_sha256=digest(OUT/'manifest.json')))
 print('FOCUS_PREREGISTRATION_EXPORTED',len(checks),flush=True)

def archive():
 target=OUT/'archive';assert not target.exists();target.mkdir();files={};key=os.environ['DEEPSEEK_API_KEY'].encode()
 for p in list(OUT.rglob('*')):
  if not p.is_file() or target in p.parents:continue
  raw=p.read_bytes();assert key not in raw;dest=target/(str(p.relative_to(OUT))+'.gz');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  files[str(dest.relative_to(target))]=dict(source_sha256=digest(p),gzip_sha256=digest(dest))
 write(target/'manifest.json',dict(files=files,all_attempts_kept=True,lossless=True,credential_absent=True))

def run():
 m,f=verify();rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert rev==remote
 for p,s in read(OUT/'publication.json')['git_files'].items():assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==s,p
 assert balance(),'No available balance before first new task'
 with (OUT/'started.lock').open('x') as stream:stream.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),revision=rev));finished=[];attempts=[]
 try:
  for task in m['tasks']:
   verify();retry=0
   while True:
    calls=common.calls_under(OUT/'runs');first=[c for c in calls if '_quota_recovery1' not in Path(c['source']).parent.name]
    assert len(calls)+64<=384 and sum(c.get('attempt')==1 for c in calls)+32<=192
    if retry==0:assert len(first)+64<=192 and sum(c.get('attempt')==1 for c in first)+32<=96
    label=task['task']+('_quota_recovery1' if retry else '');directory=OUT/'runs'/label
    write(OUT/'progress.json',dict(status='running',current_task=label,completed_tasks=finished,total_tasks=3,reused_model_seeds=[11,12]))
    cmd=[sys.executable,'-u',str(HERE/'runner.py'),'--seed',str(task['seed']),'--run-name',label,'--input-file',f['input_path'],'--training-directory',str(core.training(task['seed'])),'--output-root',str(OUT/'runs'),'--methods',*runner.METHODS,'--phase','development']
    with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:process=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    records=read(directory/'calls.json') if (directory/'calls.json').exists() else [];assert len(records)<=64 and sum(c.get('attempt')==1 for c in records)<=32
    fatal=next((c.get('failure') for c in records if c.get('failure') in ('HTTP_401','HTTP_402','HTTP_403')),None);attempts.append(dict(label=label,http=len(records),exit_code=process.returncode,fatal=fatal));write(OUT/'attempts.json',attempts)
    if process.returncode==0:break
    if fatal=='HTTP_402' and retry==0:
     while True:
      write(OUT/'progress.json',dict(status='waiting_for_balance',current_task=label,completed_tasks=finished,total_tasks=3));time.sleep(1800)
      if balance():break
     retry=1;continue
    raise RuntimeError(f'{label}: {fatal or "program/audit failure"}; preserve and diagnose')
   auditor.audit(runner,directory,read(Path(f['input_path'])),f['contracts'][str(task['seed'])]['expected_parameter_sha256'])
   finished.append(dict(task,label=label,audit_sha256=digest(directory/'audit.json')));verify();write(OUT/'progress.json',dict(status='running',completed_tasks=finished,total_tasks=3))
  s=analysis.summarize(runner,OUT,finished,common);write(OUT/'completed.json',dict(total_episodes=40,new_episodes=24,node_periods=24000,completed_tasks=finished,post_selected_development=True))
  write(OUT/'progress.json',dict(status='completed',completed_tasks=finished,total_tasks=3));archive()
 except Exception as e:write(OUT/'failed.json',dict(error=type(e).__name__,detail=str(e),completed_tasks=finished,preserved=True));raise

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','publish','verify','run'));a=p.parse_args();common.key_from_user();{'register':register,'publish':publish,'verify':verify,'run':run}[a.action]()
