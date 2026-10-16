"""Existing z2 Base-stock on fixed Sundial paths, API0, no retuning or RL rerun."""
import argparse,csv,gzip,hashlib,importlib.util,json,os,socket,subprocess,sys,time,traceback,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
OUT=ROOT/'results/sundial_fixed_base_stock/v1';INPUT=ROOT/'results/submission_required/v1/inputs/confirmation01_main.json'
PLAN=ROOT/'docs/superpowers/plans/2026-10-16-sundial-fixed-base-stock.md'
KINDS=('single_surge','sustained_surge','double_surge');CONFIG=dict(name='local_z2_frozen',z=2,information='local',rounding='ceil')
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
policy=module('fixed_baseline_original_policy',ROOT/'experiments/base_stock_baseline/policy.py')
previous=sys.modules.get('policy');sys.modules['policy']=policy
try:bs=module('fixed_original_baseline_episode',ROOT/'experiments/base_stock_baseline/batch.py')
finally:
 if previous is None:sys.modules.pop('policy',None)
 else:sys.modules['policy']=previous
assert bs.BaseStock is policy.BaseStock
numerical=module('fixed_explicit_scalar_auditor',ROOT/'experiments/online_llm_artifacts/audit_base_stock_numerical.py')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def key_bytes():
 try:
  with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as e:return winreg.QueryValueEx(e,'DEEPSEEK_API_KEY')[0].encode()
 except OSError:return b''
def sources():
 files=list(HERE.glob('*.py'))+[PLAN,INPUT,ROOT/'experiments/base_stock_baseline/policy.py',ROOT/'experiments/base_stock_baseline/batch.py',ROOT/'experiments/online_llm_artifacts/audit_base_stock_numerical.py',ROOT/'results/base_stock_baseline/development_v1/summary.json',Path(sys.executable)]
 files+=list((ROOT/'external/liu-inventory').rglob('*.py'))
 return {str(p):sha(p) for p in files}
def references():
 items=[]
 for seed in range(11,16):
  guard=ROOT/f'results/online_llm_guard_pool/development_v1/runs/development_batch01_seed{seed}'
  base='sundial_six_rules/development_v1' if seed<13 else 'sundial_six_rules_extension/v1'
  sundial=ROOT/f'results/{base}/runs/seed{seed}_four_types'
  items.extend([dict(seed=seed,method='happo',group='happo',path=str(guard)),dict(seed=seed,method='full_merton',group='guard_pool',path=str(guard)),dict(seed=seed,method='full_sundial',group='adapted_sundial',path=str(sundial))])
 return items
def archive(directory,files):
 assert not directory.exists();directory.mkdir(parents=True);key=key_bytes();entries={}
 for i,p in enumerate(dict.fromkeys(files)):
  raw=p.read_bytes();assert not key or key not in raw
  target=directory/f'{i:03d}.gz';target.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(target.read_bytes())==raw
  entries[target.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=sha(p),gzip_sha256=sha(target))
 write(directory/'manifest.json',dict(files=entries,lossless=True,credential_absent=True,large_weights_not_copied=True))
 return {**{p:v['gzip_sha256'] for p,v in entries.items()},(directory/'manifest.json').relative_to(ROOT).as_posix():sha(directory/'manifest.json')}
def verify():
 v=read(OUT/'registration.json')
 for p,h in v['files'].items():assert sha(p)==h,p
 return v
def register():
 assert not OUT.exists();assert read(ROOT/'results/base_stock_baseline/development_v1/summary.json')['selected_z']['local']==2
 files=sources();refs=references()
 for item in refs:
  for p in Path(item['path']).iterdir():
   if p.is_file():files[str(p)]=sha(p)
 OUT.mkdir(parents=True)
 write(OUT/'registration.json',dict(files=files,references=refs,input=str(INPUT),config=CONFIG,api=0,new_rl_rollouts=0,new_episodes=6,new_rows=3600,posthoc=True,independent_confirmation=False,created=time.time()))
 public=archive(ROOT/'docs/artifacts/sundial_fixed_base_stock_preregistration_v1',[*HERE.glob('*.py'),PLAN,OUT/'registration.json'])
 write(OUT/'publication.json',dict(files=public));print('FIXED_BASE_STOCK_REGISTERED',len(files),flush=True)
def published():
 v=verify();head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert head==remote
 check_publication(OUT/'publication.json');return v,head
def check_publication(path):
 for p,h in read(path)['files'].items():assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==h,p
def cached_costs(registration,data):
 values=[];loaded={}
 for item in registration['references']:
  p=Path(item['path']);done=read(p/'completed.json');assert not done['runtime_failures'] and all(x['unchanged'] for x in done['parameter_checks'].values())
  old=read(p/'demands.json')
  assert all(old[k][:3]==data[k][:3] for k in ('base','shock','events'))
  if str(p) not in loaded:
   with (p/'periods.csv').open(encoding='utf-8',newline='') as f:loaded[str(p)]=list(csv.DictReader(f))
  rows=loaded[str(p)];episodes=read(p/'episodes.json')
  for trace in range(3):
   for scenario in ('base','shock'):
    local=[x for x in rows if x['group']==item['group'] and x['scenario']==scenario and int(x['trace'])==trace]
    assert len(local)==600 and len({(x['period'],x['node']) for x in local})==600
    for x in local:
     assert float(x['cost'])==int(x['inventory'])+int(x['backlog'])
     assert int(x['demand'])==data['base' if scenario=='base' else 'shock'][trace][int(x['period'])-1]
    cost=sum(float(x['cost']) for x in local)/600
    e=next(x for x in episodes if x['group']==item['group'] and x['scenario']==scenario and x['trace']==trace);assert abs(cost-e['cost'])<1e-10
    values.append(dict(seed=item['seed'],method=item['method'],trace=trace,type=KINDS[trace],scenario=scenario,cost=cost))
 return values
def run():
 registration,head=published()
 with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),revision=head,api=0));start=time.perf_counter()
 def forbidden(*a,**kw):raise RuntimeError('Network forbidden after registered preflight')
 socket.socket.connect=forbidden;socket.create_connection=forbidden
 try:
  data=read(INPUT);assert [x['type'] for x in data['events'][:3]]==list(KINDS)
  historic=cached_costs(registration,data);write(OUT/'cached_comparison.json',historic);scores=[];all_rows=[];prefix={}
  for trace in range(3):
   for scenario in ('base','shock'):
    verify();write(OUT/'progress.json',dict(status='running',trace=trace,scenario=scenario,completed_episodes=len(scores),total_episodes=6,api=0))
    result=bs.episode(data[scenario][trace],**{k:v for k,v in CONFIG.items() if k!='name'});rows=result.pop('rows')
    cost=numerical.verify_episode(rows,data[scenario][trace],CONFIG);assert abs(cost-result['cost'])<1e-10
    assert result['ledger_verified'] and len(rows)==600
    if scenario=='base':prefix[trace]=rows
    else:
     for x,y in zip(prefix[trace],rows):
      if int(y['period'])>=data['events'][trace]['start_index']:break
      assert all(x[k]==y[k] for k in ('inventory','backlog','action','cost','target','position','demand','after_unshipped'))
    folder=OUT/'runs'/f'trace{trace}_{scenario}';folder.mkdir(parents=True)
    identity=dict(method='base_stock_z2',trace=trace,type=KINDS[trace],scenario=scenario)
    with gzip.open(folder/'periods.csv.gz','wt',encoding='utf-8',newline='') as f:
     writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write(folder/'audit.json',dict(passed=True,cost_recomputed=True,ledger=True,causal=True,rows=600,api=0))
    scores.append(dict(**identity,**result));all_rows.extend(dict(**identity,**x) for x in rows);write(OUT/'episodes.json',scores)
  write(OUT/'numerical_boundaries.json',numerical.BOUNDARIES)
  assert len(scores)==6 and len(all_rows)==3600
  table=[];per_seed=[]
  for trace,kind in enumerate(KINDS):
   means={m:sum(x['cost'] for x in historic if x['method']==m and x['scenario']=='shock' and x['trace']==trace)/5 for m in ('happo','full_merton','full_sundial')}
   base=next(x['cost'] for x in scores if x['trace']==trace and x['scenario']=='shock');means['base_stock_z2']=base
   table.append(dict(type=kind,**means,sundial_vs_base_percent=100*(means['full_sundial']/base-1)))
   for seed in range(11,16):per_seed.append(dict(seed=seed,type=kind,base_stock_z2=base,**{m:next(x['cost'] for x in historic if x['seed']==seed and x['method']==m and x['scenario']=='shock' and x['trace']==trace) for m in ('happo','full_merton','full_sundial')}))
  means={m:sum(x[m] for x in table)/3 for m in ('happo','full_merton','full_sundial','base_stock_z2')}
  verify();write(OUT/'summary.json',dict(by_type=table,overall=means,per_seed=per_seed,new_episodes=6,new_rows=3600,api=0,deterministic_no_training_seeds=True,independent_paths=3,posthoc=True,no_significance_claim=True,rule_limits=dict(full_merton=4,full_sundial=6),baseline_information='completed local demands; different from LLM global state/reports/notification'))
  write(OUT/'completed.json',dict(episodes=6,rows=3600,api=0,seconds=time.perf_counter()-start,all_scalar_audits_passed=True,cache_costs_recomputed=True))
  write(OUT/'progress.json',dict(status='completed',completed_episodes=6,api=0))
  public=archive(ROOT/'docs/artifacts/sundial_fixed_base_stock_completed_v1',[p for p in OUT.rglob('*') if p.is_file()]+list(HERE.glob('*.py'))+[PLAN])
  write(OUT/'completed_publication.json',dict(files=public));print('FIXED_BASE_STOCK_COMPLETED',json.dumps(means),flush=True)
 except Exception as e:
  write(OUT/'failed.json',dict(error=type(e).__name__,detail=str(e),preserved=True,api=0));traceback.print_exc();raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','verify','run','check-publication'));a=p.parse_args()
 {'register':register,'verify':verify,'run':run,'check-publication':lambda:check_publication(OUT/'completed_publication.json')}[a.action]()
