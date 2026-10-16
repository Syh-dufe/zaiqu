"""Serial fixed-path extension; bounded paid calls and preserved failed attempts."""
import argparse,csv,gzip,hashlib,importlib.util,json,os,subprocess,sys,time,traceback,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=ROOT/'results/seeds16_20_fixed_comparison/v2'
SPEC=ROOT/'docs/superpowers/specs/2026-10-16-seeds16-20-fixed-comparison-design.md';PLAN=ROOT/'docs/superpowers/plans/2026-10-16-seeds16-20-fixed-comparison.md'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
ref=module('extension_lossless_archive_reference',ROOT/'experiments/base_stock_recalibration/batch.py');read=ref.read;write=ref.write;sha=ref.sha
PYTHON=Path('C:/Users/13384/.codex/worktrees/delivery-happo/新/.venv/Scripts/python.exe')
SOURCE=ROOT/'results/submission_required/v1/inputs/confirmation01_main.json'
def sources():
 r=module('extension_prepare_runner',HERE/'runner.py');r.setup('sundial',16)
 files={str(ROOT/p):h for p,h in r.core.source_hashes().items()}
 files[str(r.predictor.ADAPTER)]=sha(r.predictor.ADAPTER)
 for p in r.predictor.base.base.MODEL.rglob('*'):
  if p.is_file():files[str(p)]=sha(p)
 contracts={}
 for seed in range(16,21):
  _,v=r.core.load_policy('happo',seed);contracts[str(seed)]=v;files.update(v['hashes'])
 for p in [SOURCE,SPEC,PLAN,*HERE.glob('*.py'),PYTHON]:files[str(p)]=sha(p)
 for p in (ROOT/'results/seeds16_20_fixed_comparison/v1').rglob('*'):
  if p.is_file():files[str(p)]=sha(p)
 return files,contracts
def verify():
 r=read(OUT/'registration.json')
 for p,h in r['files'].items():assert sha(Path(p))==h,p
 return r
def command(seed,mode,path,offline=False,reference=None):
 v=[str(PYTHON),'-u',str(HERE/'runner.py'),'--seed',str(seed),'--mode',mode,'--input',str(OUT/'input.json'),'--out',str(path)]
 if offline:v.append('--offline')
 if reference is not None:v+=['--reference',str(reference)]
 return v
def prepare():
 assert not OUT.exists();OUT.mkdir(parents=True)
 files,contracts=sources();data=read(SOURCE)
 data={k:(v[:3] if k in ('base','shock','events') else v) for k,v in data.items()}
 write(OUT/'input.json',data);files[str(OUT/'input.json')]=sha(OUT/'input.json')
 write(OUT/'preparation_freeze.json',dict(files=files,contracts=contracts,api=0))
 for mode in ('merton','sundial'):
  label=f'fixture_seed16_{mode}';folder=OUT/'fixture'/label
  reference=OUT/'fixture/fixture_seed16_merton' if mode=='sundial' else None
  with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:
   p=subprocess.run(command(16,mode,folder,True,reference),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
  assert p.returncode==0,f'Preserve fixture failure: {label}'
 for p,h in files.items():assert sha(Path(p))==h,p
 write(OUT/'preflight.json',dict(status='passed',all_five_model_contracts=True,fixture_episodes=18,fixture_rows=10800,api=0,fake_rules_not_performance=True))
 print('EXTENSION_PREFLIGHT_PASSED',flush=True)
def register():
 assert not (OUT/'registration.json').exists();assert read(OUT/'preflight.json')['status']=='passed'
 prep=read(OUT/'preparation_freeze.json');files=dict(prep['files'])
 for p,h in files.items():assert sha(Path(p))==h,p
 for p in OUT.rglob('*'):
  if p.is_file():files[str(p)]=sha(p)
 # Bind previous five-model and all Base-stock rows without rerunning them.
 prior=[ROOT/'results/sundial_fixed_base_stock/v2/summary.json',ROOT/'results/sundial_fixed_base_stock/v2/cached_comparison.json',ROOT/'results/base_stock_recalibration/v1/summary.json',ROOT/'results/base_stock_zero_history/v1/summary.json']
 for p in prior:files[str(p)]=sha(p)
 tasks=[dict(seed=s,mode=m,label=f'seed{s}_{m}',episodes=12 if m=='merton' else 6,max_http=48,max_semantic=24) for s in range(16,21) for m in ('merton','sundial')]
 write(OUT/'registration.json',dict(files=files,contracts=prep['contracts'],tasks=tasks,episodes=90,rows=54000,first_http_cap=480,first_semantic_cap=240,total_http_cap=960,total_semantic_cap=480,max_quota_recovery_per_task=1,rule_limits=dict(merton=4,sundial=6),exposed_paths=True,all_seeds_retained=True,created=time.time()))
 paths=[p for p in OUT.rglob('*') if p.is_file()]+list(HERE.glob('*.py'))+[SPEC,PLAN]
 paths += [p for p in (ROOT/'results/seeds16_20_fixed_comparison/v1').rglob('*') if p.is_file()]
 public=ref.reuse.archive(ROOT/'docs/artifacts/seeds16_20_fixed_comparison_preregistration_v2',paths)
 write(OUT/'publication.json',dict(files=public));print('EXTENSION_REGISTERED',flush=True)
def calls():
 return [dict(source=str(p),**x) for p in (OUT/'runs').rglob('calls.json') for x in read(p)] if (OUT/'runs').exists() else []
def balance():
 common=module('extension_secure_balance',ROOT/'experiments/submission_required/common.py');common.key_from_user()
 req=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY']})
 with urllib.request.urlopen(req,timeout=30) as r:v=json.loads(r.read())
 value=v.get('is_available') is True
 path=OUT/'balance_checks.json';log=read(path) if path.exists() else [];log.append(dict(time=time.time(),available=value));write(path,log);return value
def archive():
 files=[p for p in OUT.rglob('*') if p.is_file() and p.name not in ('driver.log','error.log')]+list(HERE.glob('*.py'))+[SPEC,PLAN]
 public=ref.reuse.archive(ROOT/'docs/artifacts/seeds16_20_fixed_comparison_completed_v2',files)
 write(OUT/'completed_publication.json',dict(files=public,active_wrapper_logs_excluded=True))
def summarize(finished):
 episodes=[]
 for job in finished:
  for e in read(Path(job['directory'])/'episodes.json'):episodes.append(dict(seed=job['seed'],mode=job['mode'],**e))
 assert len(episodes)==90
 old=read(ROOT/'results/sundial_fixed_base_stock/v2/cached_comparison.json');names={'happo':'happo','original_merton':'full_merton','adapted_sundial':'full_sundial'}
 new=[dict(seed=x['seed'],method=names[x['group']],trace=x['trace'],type=('single_surge','sustained_surge','double_surge')[x['trace']],scenario=x['scenario'],cost=x['cost']) for x in episodes]
 all_rows=old+new
 def table(values):
  return {scenario:{kind:{m:sum(x['cost'] for x in values if x['scenario']==scenario and x['type']==kind and x['method']==m)/sum(x['scenario']==scenario and x['type']==kind and x['method']==m for x in values) for m in names.values()} for kind in ('single_surge','sustained_surge','double_surge')} for scenario in ('base','shock')}
 records=calls();assert len(records)<=960 and sum(x['attempt']==1 for x in records)<=480
 common=module('extension_usage',ROOT/'experiments/submission_required/common.py')
 write(OUT/'summary.json',dict(new_episodes=90,new_rows=54000,reused_episodes=len(old),new_seed_costs=table(new),all_ten_costs=table(all_rows),per_seed_episodes=all_rows,http=len(records),semantic=sum(x['attempt']==1 for x in records),usage=common.usage(records),base_stock_zero_history=read(ROOT/'results/base_stock_zero_history/v1/summary.json'),base_stock_standard=read(ROOT/'results/base_stock_recalibration/v1/summary.json')['fixed_by_type'],posthoc=True,independent_paths=3,rule_limits=dict(merton=4,sundial=6),not_predictor_only=True))
def run():
 r=verify();ref.old.check_publication(OUT/'publication.json')
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert remote==head
 with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),revision=head));finished=[];attempts=[]
 try:
  assert balance(),'Balance unavailable; preserve stopped driver'
  for task in r['tasks']:
   verify();retry=0
   while True:
    records=calls();first=[x for x in records if '_quota_recovery1' not in x['source']]
    assert len(records)+48<=960 and sum(x['attempt']==1 for x in records)+24<=480
    if retry==0:assert len(first)+48<=480 and sum(x['attempt']==1 for x in first)+24<=240
    label=task['label']+('_quota_recovery1' if retry else '');folder=OUT/'runs'/label;reference=None
    if task['mode']=='sundial':reference=Path(next(x['directory'] for x in finished if x['seed']==task['seed'] and x['mode']=='merton'))
    write(OUT/'progress.json',dict(status='running',current_task=label,completed_tasks=finished,total_tasks=10,completed_episodes=sum(x['episodes'] for x in finished)))
    with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:p=subprocess.run(command(task['seed'],task['mode'],folder,False,reference),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    raw=read(folder/'calls.json') if (folder/'calls.json').exists() else [];assert len(raw)<=48 and sum(x['attempt']==1 for x in raw)<=24
    fatal=next((x.get('failure') for x in raw if x.get('failure') in ('HTTP_401','HTTP_402','HTTP_403')),None)
    attempts.append(dict(label=label,seed=task['seed'],mode=task['mode'],exit_code=p.returncode,http=len(raw),semantic=sum(x['attempt']==1 for x in raw),fatal=fatal));write(OUT/'attempts.json',attempts)
    if p.returncode==0:break
    if fatal=='HTTP_402' and retry==0:
     while True:
      write(OUT/'progress.json',dict(status='waiting_for_balance',current_task=label,completed_tasks=finished,next_check_seconds=1800))
      for _ in range(60):time.sleep(30)
      if balance():break
     retry=1;continue
    raise RuntimeError(f'Task stopped without overwrite: {label}, fatal={fatal}, exit={p.returncode}')
   audit=read(folder/'audit.json');assert audit['status']=='passed' and audit['model_seed']==task['seed']
   finished.append(dict(seed=task['seed'],mode=task['mode'],directory=str(folder),episodes=task['episodes'],audit_sha256=sha(folder/'audit.json')));write(OUT/'finished.json',finished)
  verify();summarize(finished);write(OUT/'completed.json',dict(tasks=10,episodes=90,rows=54000,all_task_audits_passed=True,api_in_summary=True));write(OUT/'progress.json',dict(status='completed',completed_tasks=finished,completed_episodes=90));archive();print('SEEDS16_20_COMPARISON_COMPLETED',flush=True)
 except Exception as e:write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),completed_tasks=finished,preserved=True));traceback.print_exc();raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','register','run','verify','balance'));a=p.parse_args();{'prepare':prepare,'register':register,'run':run,'verify':verify,'balance':balance}[a.action]()
