"""Registered real-API pilot; no automatic retry, preserve all failed requests."""
import argparse,gzip,hashlib,importlib.util,json,os,subprocess,sys,time,urllib.request,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=ROOT/'experiments/sundial_cached_api'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
runner=module('registered_response_live_runner',HERE/'runner.py');core=runner.core
common=module('response_live_protected_common',ROOT/'experiments/submission_required/common.py');auditor=module('response_live_explicit_audit',HERE/'audit.py')
read,write,sha=common.read,common.write,common.digest
OUT=ROOT/'results/sundial_cached_api/development_v1';FIXTURE=ROOT/'results/sundial_cached_api/no_api_fixture_v1';INPUT=ROOT/'results/sundial_closed_loop_development/development_v2/inputs/stationary.json'
PACKAGE=ROOT/'docs/artifacts/sundial_cached_api_preregistration_v1'
def available():
 request=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY']})
 with urllib.request.urlopen(request,timeout=30) as response:v=json.loads(response.read())
 return v.get('is_available') is True
def register():
 assert not OUT.exists() and read(FIXTURE/'preflight_passed.json')['network_requests']==0
 selection=ROOT/'results/sundial_change_response_recovery/v1/selection.json';assert read(selection)['winner']=='all_half' and read(selection)['gate_passed']
 files={str(ROOT/p):v for p,v in core.source_hashes().items()}
 for p in list(FIXTURE.rglob('*'))+[Path(__file__),selection,INPUT,runner.predictor.ADAPTER,ROOT/'results/sundial_change_response_recovery/v1/completed.json']:
  if p.is_file():files[str(p)]=sha(p)
 for p in runner.predictor.base.base.MODEL.rglob('*'):
  if p.is_file():files[str(p)]=sha(p)
 contracts={str(seed):core.contracts(INPUT,core.LIBRARY,core.training(seed)) for seed in (11,12)}
 for c in contracts.values():
  for name in ('happo_contract','ippo_contract'):files.update(c[name]['hashes'])
 old_bound={}
 for seed,c in contracts.items():
  ref=ROOT/f'results/sundial_closed_loop_development/development_v2/runs/batch01_seed{seed}';p=read(ref/'protocol.json')
  assert read(ref/'audit.json')['status']=='passed' and p['input_sha256']==sha(INPUT) and p['system']==core.SYSTEM and p['expected_parameter_sha256']==c['expected_parameter_sha256']
  for path in ref.rglob('*'):
   if path.is_file():old_bound[str(path)]=sha(path)
 stopped=ROOT/'results/sundial_response_live_api/development_v1';assert read(stopped/'progress.json')['no_restart']
 for path in stopped.rglob('*'):
  if path.is_file():old_bound[str(path)]=sha(path)
 files.update(old_bound)
 OUT.mkdir(parents=True)
 registration=dict(files=files,contracts=contracts,input_path=str(INPUT),input_sha256=sha(INPUT),system_sha256=hashlib.sha256(core.SYSTEM.encode()).hexdigest(),seeds=[11,12],methods=list(runner.METHODS),episodes=16,rows=9600,api_first_http=128,api_first_semantic=64,max_http_per_task=64,max_semantic_per_task=32,no_automatic_reruns=True,actual_variant='response_all_half_real_guard_pool',old_outage_not_resumed=True)
 write(OUT/'registration.json',registration);write(OUT/'api_precheck.json',dict(balance_available=available(),official_status_url='https://status.deepseek.com/',official_status='operational when checked via web before pilot',old_outage_attempts_separate=6,stopped_newpath_attempts_separate=29))
 assert not PACKAGE.exists();PACKAGE.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 paths=[Path(p) for p in old_bound]+[ROOT/p for p in core.source_hashes()]+[Path(__file__),selection,INPUT,runner.predictor.ADAPTER,OUT/'registration.json',OUT/'api_precheck.json']+[p for p in FIXTURE.rglob('*') if p.is_file()]
 entries={}
 for i,p in enumerate(dict.fromkeys(paths)):
  raw=p.read_bytes();assert key not in raw;dest=PACKAGE/f'{i:03d}.gz';dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=sha(p),gzip_sha256=sha(dest))
 (PACKAGE/'manifest.json').write_bytes(json.dumps(dict(files=entries,lossless=True,credential_absent=True,weights_local_only=True),indent=2).encode());write(OUT/'publication.json',dict(files={p:v['gzip_sha256'] for p,v in entries.items()}));verify();print('RESPONSE_LIVE_REGISTERED',len(entries),flush=True)
def verify():
 r=read(OUT/'registration.json')
 for p,v in r['files'].items():assert sha(p)==v,p
 assert core.source_hashes()==r['contracts']['11']['source_sha256']
 assert hashlib.sha256(core.SYSTEM.encode()).hexdigest()==r['system_sha256']
 return r
def run():
 r=verify();revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert revision==remote
 for p,v in read(OUT/'publication.json')['files'].items():assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==v
 assert available(),'No available balance before pilot'
 with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),revision=revision));completed=[];summary=[]
 try:
  for seed in r['seeds']:
   verify();existing=common.calls_under(OUT/'runs');assert len(existing)+64<=128 and sum(c.get('attempt')==1 for c in existing)+32<=64
   label=f'seed{seed}_four_types';write(OUT/'progress.json',dict(status='running',task=label,completed=completed,total_tasks=2,api_http_so_far=len(existing)))
   cmd=[sys.executable,'-u',str(HERE/'runner.py'),'--seed',str(seed),'--run-name',label,'--input-file',str(INPUT),'--training-directory',str(core.training(seed)),'--output-root',str(OUT/'runs'),'--phase','development']
   with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:p=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
   assert p.returncode==0,f'{label}: API/program failure; preserve partial records and diagnose'
   directory=OUT/'runs'/label;auditor.audit(runner,directory,read(INPUT),r['contracts'][str(seed)]['expected_parameter_sha256'])
   summary.extend(dict(e,seed=seed) for e in read(directory/'episodes.json'));completed.append(seed);verify();write(OUT/'summary.json',summary)
   calls=common.calls_under(OUT/'runs');assert len(calls)<=128 and sum(c.get('attempt')==1 for c in calls)<=64
  write(OUT/'completed.json',dict(episodes=16,rows=9600,api_http=len(calls),semantic=sum(c.get('attempt')==1 for c in calls),seeds=completed));write(OUT/'progress.json',dict(status='completed',completed=completed,total_tasks=2,api_http=len(calls)))
 except Exception as e:
  write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),completed=completed,preserved=True,no_automatic_reruns=True));write(OUT/'progress.json',dict(status='stopped_for_diagnosis',completed=completed,total_tasks=2));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run','verify'));a=p.parse_args();common.key_from_user();{'register':register,'run':run,'verify':verify}[a.action]()

