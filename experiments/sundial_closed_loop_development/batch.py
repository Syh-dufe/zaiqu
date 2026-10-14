"""Unique frozen serial development batch, all failures and quota attempts retained."""
import argparse,gzip,hashlib,json,os,subprocess,sys,time,urllib.request
from pathlib import Path
import runner
ROOT=runner.ROOT;HERE=runner.HERE;core=runner.core
common=runner.module('sundial_batch_common',ROOT/'experiments/submission_required/common.py')
analysis=runner.module('sundial_explicit_cost_analysis',HERE/'analyze.py');auditor=runner.module('sundial_explicit_cost_auditor',HERE/'audit.py')
read,write,digest=common.read,common.write,common.digest
OUT=ROOT/'results/sundial_closed_loop_development/development_v2';PACKAGE=ROOT/'docs/artifacts/sundial_closed_loop_development_v2_preregistration'

def balance():
 request=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY']})
 with urllib.request.urlopen(request,timeout=30) as response:value=json.loads(response.read())
 return value.get('is_available') is True

def verify():
 m=read(OUT/'manifest.json');f=read(OUT/'freeze.json')
 assert digest(OUT/'freeze.json')==m['freeze_sha256'] and core.source_hashes()==f['source_sha256']
 assert hashlib.sha256(core.SYSTEM.encode()).hexdigest()==f['system_sha256'] and digest(runner.predictor.ADAPTER)==f['adapter_sha256']
 assert digest(f['source_inputs'])==f['source_inputs_sha256']
 for p,sha in f['dependencies'].items():assert digest(p)==sha,p
 for inp in m['inputs'].values():assert digest(inp['path'])==inp['sha256']
 if (OUT/'registration.json').exists():
  registration=read(OUT/'registration.json');assert digest(sys.executable)==registration['executable_sha256']
  for contract in registration['contracts'].values():
   for label in ('happo_contract','ippo_contract'):
    for p,sha in contract[label]['hashes'].items():assert digest(p)==sha,p
 return m,f

def register():
 m,f=verify();assert not (OUT/'registration.json').exists()
 fixture=ROOT/'results/sundial_closed_loop_development/no_api_fixture_v1/preflight_passed.json';value=read(fixture)
 assert value['status']=='passed' and value['network_requests']==0 and value['recorded_sundial_inference_reproduced']
 contracts={str(s):core.contracts(Path(m['inputs']['1']['path']),core.LIBRARY,core.training(s)) for s in range(11,16)}
 for task in m['tasks']:
  check=core.contracts(Path(m['inputs'][str(task['batch'])]['path']),core.LIBRARY,core.training(task['seed']))
  assert check['expected_parameter_sha256']==contracts[str(task['seed'])]['expected_parameter_sha256']
 write(OUT/'registration.json',dict(contracts=contracts,fixture_sha256=digest(fixture),source_sha256=f['source_sha256'],executable_sha256=digest(sys.executable),
  api_model='deepseek-flash',tasks=15,episodes=480,node_periods=288000,first_caps=[3840,1920],cumulative_caps=[7680,3840],fixture_episodes=32))
 print('REGISTERED_15_CONTRACTS_480_EPISODES',flush=True)

def publish():
 m,f=verify();assert not PACKAGE.exists();registration=read(OUT/'registration.json')
 files=[ROOT/p for p in f['source_sha256']]+[OUT/n for n in ('freeze.json','manifest.json','registration.json')]+[Path(x['path']) for x in m['inputs'].values()]
 files += [runner.predictor.ADAPTER]+[p for p in (ROOT/'results/sundial_closed_loop_development/no_api_fixture_v1').rglob('*') if p.is_file()]
 PACKAGE.mkdir(parents=True);checks={};origins={};key=os.environ['DEEPSEEK_API_KEY'].encode()
 for index,p in enumerate(dict.fromkeys(files)):
  blob=p.read_bytes();assert key not in blob
  dest=PACKAGE/'files'/f'{index:04d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(blob,mtime=0));assert gzip.decompress(dest.read_bytes())==blob
  rel=dest.relative_to(ROOT).as_posix();checks[rel]=digest(dest);origins[rel]=dict(source=str(p),sha256=digest(p))
 write(PACKAGE/'manifest.json',dict(files=checks,origins=origins,lossless=True,credential_absent=True,checkpoint_local_only=True))
 checks[(PACKAGE/'manifest.json').relative_to(ROOT).as_posix()]=digest(PACKAGE/'manifest.json')
 write(OUT/'publication.json',dict(git_files=checks,freeze_sha256=digest(OUT/'freeze.json'),manifest_sha256=digest(OUT/'manifest.json'),registration_sha256=digest(OUT/'registration.json')))
 print('SUNDIAL_COST_PREREGISTRATION_EXPORTED',len(checks),flush=True)

def archive():
 target=OUT/'archive';assert not target.exists();target.mkdir();entries={};key=os.environ['DEEPSEEK_API_KEY'].encode()
 for p in list(OUT.rglob('*')):
  if not p.is_file() or target in p.parents:continue
  blob=p.read_bytes();assert key not in blob;dest=target/(str(p.relative_to(OUT))+'.gz');dest.parent.mkdir(parents=True,exist_ok=True)
  dest.write_bytes(gzip.compress(blob,mtime=0));assert gzip.decompress(dest.read_bytes())==blob
  entries[str(dest.relative_to(target))]=dict(source_sha256=digest(p),gzip_sha256=digest(dest))
 write(target/'manifest.json',dict(files=entries,all_attempts_preserved=True,lossless=True,credential_absent=True))

def run():
 m,f=verify();rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert rev==remote,'Push registration first'
 publication=read(OUT/'publication.json')
 for p,sha in publication['git_files'].items():assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==sha,p
 assert digest(OUT/'registration.json')==publication['registration_sha256']
 assert balance(),'No available balance before first task'
 with (OUT/'started.lock').open('x') as stream:stream.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),revision=rev));finished=[];attempts=[];registration=read(OUT/'registration.json')
 try:
  for task in m['tasks']:
   verify();retry=0
   while True:
    calls=common.calls_under(OUT/'runs');first=[c for c in calls if '_quota_recovery1' not in Path(c['source']).parent.name]
    assert len(calls)+256<=7680 and sum(c.get('attempt')==1 for c in calls)+128<=3840
    if retry==0:assert len(first)+256<=3840 and sum(c.get('attempt')==1 for c in first)+128<=1920
    label=task['task']+('_quota_recovery1' if retry else '');directory=OUT/'runs'/label
    write(OUT/'progress.json',dict(status='running',current_task=label,completed_tasks=finished,total_tasks=15))
    command=[sys.executable,'-u',str(HERE/'runner.py'),'--seed',str(task['seed']),'--batch',str(task['batch']),'--run-name',label,'--input-file',m['inputs'][str(task['batch'])]['path'],
      '--training-directory',str(core.training(task['seed'])),'--output-root',str(OUT/'runs'),'--methods',*runner.METHODS,'--phase','development']
    with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:process=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    records=read(directory/'calls.json') if (directory/'calls.json').exists() else [];assert len(records)<=256 and sum(c.get('attempt')==1 for c in records)<=128
    fatal=next((c.get('failure') for c in records if c.get('failure') in ('HTTP_401','HTTP_402','HTTP_403')),None)
    attempts.append(dict(label=label,http=len(records),exit_code=process.returncode,fatal=fatal));write(OUT/'attempts.json',attempts)
    if process.returncode==0:break
    if fatal=='HTTP_402' and retry==0:
     while True:
      write(OUT/'progress.json',dict(status='waiting_for_balance',current_task=label,completed_tasks=finished,total_tasks=15));time.sleep(1800)
      if balance():break
     retry=1;continue
    raise RuntimeError(f'{label}: {fatal or "program/audit failure"}; preserve and diagnose')
   auditor.audit(runner,directory,read(m['inputs'][str(task['batch'])]['path']),registration['contracts'][str(task['seed'])]['expected_parameter_sha256'])
   finished.append(dict(task,label=label,audit_sha256=digest(directory/'audit.json')));verify()
   write(OUT/'progress.json',dict(status='running',completed_tasks=finished,total_tasks=15))
  summary=analysis.summarize(runner,OUT,finished,common)
  write(OUT/'completed.json',dict(episodes=480,node_periods=288000,completed_tasks=finished,fixed_gate_passed=summary['fixed_gate_passed'],training_updates=0))
  write(OUT/'progress.json',dict(status='completed',completed_tasks=finished,total_tasks=15));archive()
 except Exception as exc:
  write(OUT/'failed.json',dict(error=type(exc).__name__,detail=str(exc),completed_tasks=finished,preserved=True));raise

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=('register','verify','publish','run','balance'));opts=parser.parse_args()
 common.key_from_user()
 if opts.action=='balance':print('BALANCE_AVAILABLE',balance())
 else:{'register':register,'verify':verify,'publish':publish,'run':run}[opts.action]()
