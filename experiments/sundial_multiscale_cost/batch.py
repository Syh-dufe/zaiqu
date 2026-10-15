"""User-authorized two-model double-surge live API cost check, immutable registration."""
import argparse,gzip,hashlib,os,subprocess,sys,time,urllib.request
from pathlib import Path
import runner
ROOT=runner.ROOT;HERE=runner.HERE;core=runner.core
common=runner.module('multiscale_cost_protected_common',ROOT/'experiments/submission_required/common.py')
auditor=runner.module('multiscale_cost_auditor',HERE/'audit.py')
read,write,digest=common.read,common.write,common.digest
OUT=ROOT/'results/sundial_multiscale_cost/v1';FIXTURE=ROOT/'results/sundial_multiscale_cost/no_api_fixture_v3'
PACKAGE=ROOT/'docs/artifacts/sundial_multiscale_cost_preregistration_v1'
def balance():
 request=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY']})
 with urllib.request.urlopen(request,timeout=30) as response:return read_json_response(response).get('is_available') is True
def read_json_response(response):return __import__('json').loads(response.read())
def register():
 assert not OUT.exists();assert read(FIXTURE/'preflight_passed.json')['network_requests']==0
 OUT.mkdir(parents=True);old=read(ROOT/'results/sundial_focus_completion/v1/freeze.json');reused={}
 for seed in (14,15):
  directory=ROOT/f'results/sundial_focus_completion/v1/runs/seed{seed}_two_types';assert read(directory/'audit.json')['status']=='passed'
  for p in directory.rglob('*'):
   if p.is_file():reused[str(p)]=digest(p)
 inp=ROOT/'results/sundial_closed_loop_development/development_v2/inputs/stationary.json'
 freeze=dict(source_sha256=core.source_hashes(),dependencies=old['dependencies'],reused_sha256=reused,adapter_sha256=digest(runner.predictor.ADAPTER),input_path=str(inp),input_sha256=digest(inp),contracts={str(s):core.contracts(inp,core.LIBRARY,core.training(s)) for s in (14,15)},system_sha256=hashlib.sha256(core.SYSTEM.encode()).hexdigest(),executable_sha256=digest(sys.executable))
 write(OUT/'freeze.json',freeze);write(OUT/'manifest.json',dict(seeds=[14,15],new_episodes=4,node_periods=2400,first_http=32,first_semantic=16,cumulative_http=64,cumulative_semantic=32,actual_variant='multiscale24',post_selected_development=True))
 assert not PACKAGE.exists();PACKAGE.mkdir(parents=True);files=[ROOT/p for p in freeze['source_sha256']]+[runner.predictor.ADAPTER,OUT/'freeze.json',OUT/'manifest.json']+[p for p in FIXTURE.rglob('*') if p.is_file()]+[Path(p) for p in reused]
 files += [p for name in ('no_api_fixture_v1','no_api_fixture_v2') for p in (ROOT/'results/sundial_multiscale_cost'/name).rglob('*') if p.is_file()]+list((ROOT/'results').glob('sundial_multiscale_cost_preflight_v*.log'))
 entries={};key=os.environ['DEEPSEEK_API_KEY'].encode()
 for i,p in enumerate(dict.fromkeys(files)):
  raw=p.read_bytes();assert key not in raw;dest=PACKAGE/'files'/f'{i:03d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 write(PACKAGE/'manifest.json',dict(files=entries,lossless=True,credential_absent=True));write(OUT/'publication.json',dict(files={**{p:v['gzip_sha256'] for p,v in entries.items()},(PACKAGE/'manifest.json').relative_to(ROOT).as_posix():digest(PACKAGE/'manifest.json')}));verify();print('MULTISCALE_COST_REGISTERED',len(entries),flush=True)
def verify():
 f=read(OUT/'freeze.json');assert core.source_hashes()==f['source_sha256'] and digest(runner.predictor.ADAPTER)==f['adapter_sha256'] and digest(f['input_path'])==f['input_sha256'] and digest(sys.executable)==f['executable_sha256']
 for p,sha in {**f['dependencies'],**f['reused_sha256']}.items():assert digest(p)==sha,p
 for c in f['contracts'].values():
  for key in ('happo_contract','ippo_contract'):
   for p,sha in c[key]['hashes'].items():assert digest(p)==sha,p
 assert hashlib.sha256(core.SYSTEM.encode()).hexdigest()==f['system_sha256'];return f
def run():
 f=verify();rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert rev==remote
 for p,sha in read(OUT/'publication.json')['files'].items():assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==sha
 assert balance(),'No available balance before paid batch'
 with (OUT/'started.lock').open('x') as stream:stream.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),revision=rev));completed=[];attempts=[]
 try:
  for seed in (14,15):
   verify();retry=0
   while True:
    calls=common.calls_under(OUT/'runs');first=[c for c in calls if '_quota_recovery1' not in Path(c['source']).parent.name]
    assert len(calls)+16<=64 and sum(c.get('attempt')==1 for c in calls)+8<=32
    if retry==0:assert len(first)+16<=32 and sum(c.get('attempt')==1 for c in first)+8<=16
    label=f'seed{seed}_double'+('_quota_recovery1' if retry else '');directory=OUT/'runs'/label
    write(OUT/'progress.json',dict(status='running',current_task=label,completed_tasks=completed,total_tasks=2))
    cmd=[sys.executable,'-u',str(HERE/'runner.py'),'--seed',str(seed),'--run-name',label,'--input-file',f['input_path'],'--training-directory',str(core.training(seed)),'--output-root',str(OUT/'runs'),'--methods','adapted_sundial','--phase','development']
    with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:process=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    records=read(directory/'calls.json') if (directory/'calls.json').exists() else [];assert len(records)<=16 and sum(c.get('attempt')==1 for c in records)<=8
    fatal=next((c.get('failure') for c in records if c.get('failure') in ('HTTP_401','HTTP_402','HTTP_403')),None);attempts.append(dict(label=label,http=len(records),exit_code=process.returncode,fatal=fatal));write(OUT/'attempts.json',attempts)
    if process.returncode==0:break
    if fatal=='HTTP_402' and retry==0:
     while True:
      write(OUT/'progress.json',dict(status='waiting_for_balance',current_task=label,completed_tasks=completed,total_tasks=2));time.sleep(1800)
      if balance():break
     retry=1;continue
    raise RuntimeError(f'{label}: {fatal or "program/audit failure"}; preserve and diagnose')
   auditor.audit(runner,directory,read(Path(f['input_path'])),f['contracts'][str(seed)]['expected_parameter_sha256'])
   completed.append(dict(seed=seed,label=label));verify()
  write(OUT/'completed.json',dict(episodes=4,node_periods=2400,completed_tasks=completed,post_selected_development=True));write(OUT/'progress.json',dict(status='completed',completed_tasks=completed,total_tasks=2))
 except Exception as error:write(OUT/'failed.json',dict(error=type(error).__name__,detail=str(error),completed_tasks=completed,preserved=True));raise
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=('register','run','verify'));args=parser.parse_args();common.key_from_user();{'register':register,'run':run,'verify':verify}[args.action]()
