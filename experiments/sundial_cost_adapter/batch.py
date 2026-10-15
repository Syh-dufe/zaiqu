"""Registered serial decision-cost optimization with isolated held-out paths."""
import argparse,gzip,hashlib,json,os,subprocess,sys,time,traceback,winreg
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=ROOT/'results/sundial_cost_adapter/v1'
import runner as r
auditor=r.module('cost_adapter_explicit_independent_audit',HERE/'audit.py')
KINDS=('single_surge','sustained_surge','double_surge');SEEDS=(11,12,13,14,15)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def trace_sha(x):return hashlib.sha256(json.dumps(list(map(int,x[:200])),separators=(',',':')).encode()).hexdigest()
def parameter_file(parameters):
 tag=hashlib.sha256(json.dumps(parameters).encode()).hexdigest()[:16];path=OUT/'parameters'/f'{tag}.json'
 if not path.exists():write(path,dict(parameters=parameters))
 assert read(path)['parameters']==parameters
 return path
def execute(label,input_file,seed,parameters,methods,output):
 ledger_path=OUT/'cache_hashes.json';ledger=read(ledger_path) if ledger_path.exists() else {}
 for p,h in ledger.items():assert sha(Path(p))==h,p
 params=parameter_file(parameters);before=sha(params)
 cmd=[sys.executable,'-u',str(HERE/'runner.py'),'--seed',str(seed),'--parameters',str(params),'--methods',','.join(methods),'--run-name',label,'--input-file',str(input_file),'--training-directory',str(r.core.training(seed)),'--output-root',str(output),'--phase','development']
 log=OUT/'logs'/f'{label}.log';log.parent.mkdir(exist_ok=True)
 with log.open('x',encoding='utf-8') as f:process=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 assert process.returncode==0,f'{label} failed; preserve diagnostics'
 assert sha(params)==before
 result=auditor.audit(r,output/label,read(input_file),methods,parameters)
 for p in r.CACHE.glob('*.npz'):
  h=sha(p)
  if str(p) in ledger:assert ledger[str(p)]==h,p
  else:ledger[str(p)]=h
 write(ledger_path,ledger)
 return result
def fixture():
 assert not (OUT/'fixture_passed.json').exists();OUT.mkdir(parents=True,exist_ok=True)
 old=read(ROOT/'results/submission_required/v1/inputs/confirmation01_main.json')
 data={k:old[k][:3] for k in ('base','shock','events')};r.validate(data);p=OUT/'fixture_inputs.json';write(p,data)
 label='zero_identity_fixture_v2' if (OUT/'fixture/zero_identity_fixture').exists() else 'zero_identity_fixture'
 values=execute(label,p,11,[0.,0.,1.],('old_sundial','cost_sundial'),OUT/'fixture')
 write(OUT/'fixture_passed.json',dict(episodes=12,rows=7200,api=0,zero_identity=True,full_tail_audit=True,costs=values))
 print('COST_FIXTURE_PASSED',flush=True)
def credentials():
 try:
  with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:return winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 except OSError:return b''
def register():
 assert (OUT/'fixture_passed.json').exists() and not (OUT/'registration.json').exists()
 # Bind method before creating any new development input.
 files={str(ROOT/p):s for p,s in r.core.source_hashes().items()}
 for seed in SEEDS:
  params=parameter_file([0.,0.,1.]);r.PARAM_FILE=params
  c=r.core.contracts(OUT/'fixture_inputs.json',r.core.LIBRARY,r.core.training(seed));files.update(c['model_files']);files.update(c['happo_contract']['hashes']);files.update(c['ippo_contract']['hashes'])
 for p in r.response.base.base.MODEL.rglob('*'):
  if p.is_file():files[str(p)]=sha(p)
 files[str(r.response.ADAPTER)]=sha(r.response.ADAPTER)
 write(OUT/'method_freeze.json',dict(files=files,created=time.time(),api=0))
 gen=r.module('cost_adapter_input_generator',ROOT/'experiments/joint_baseline_confirmation/batch.py')
 used=set();bindings=[]
 for parent in (ROOT/'results',ROOT/'docs/artifacts'):
  for p in parent.rglob('*.json'):
   if OUT in p.parents:continue
   if not any(w in p.name.lower() for w in ('input','demand','historical')):continue
   try:v=read(p)
   except (ValueError,OSError):continue
   found=gen.traces_in(v)
   hashes={trace_sha(x) for x in found}
   def consumed(v):
    if isinstance(v,dict):
     if isinstance(v.get('consumed_hashes'),list):used.update(v['consumed_hashes'])
     for x in v.values():
      if isinstance(x,(dict,list)):consumed(x)
    elif isinstance(v,list):
     for x in v:
      if isinstance(x,(dict,list)):consumed(x)
   consumed(v)
   if hashes:used.update(hashes);bindings.append(dict(path=str(p),sha256=sha(p)))
 import numpy as np
 for p in (r.core.UPSTREAM/'test_data/test_demand_merton').glob('*.txt'):used.add(trace_sha(np.loadtxt(p).reshape(-1)));bindings.append(dict(path=str(p),sha256=sha(p)))
 sys.path.insert(0,str(r.core.UPSTREAM));from envs.generator import merton
 inputs=[];attempts=[];candidate=20273001
 for split,count in (('train',6),('dev',3),('holdout',5)):
  for rep in range(count):
   bases=[];shocks=[];events=[]
   for kind in KINDS:
    while True:
     assert candidate<=20273500
     seed=candidate;candidate+=1;np.random.seed(seed);base=list(map(int,merton(200,20).demand_list));shock,event=gen.profile_trace(base,kind,-10+2*rep)
     hashes={trace_sha(base),trace_sha(shock)};collision=bool(used&hashes);attempts.append(dict(seed=seed,split=split,rep=rep,type=kind,collision=collision,zero_actual_shock=base==shock))
     if not collision:used.update(hashes);break
    bases.append(base);shocks.append(shock);events.append(event)
   data=dict(base=bases,shock=shocks,events=events,split=split,repetition=rep,development_design=True);r.validate(data)
   p=OUT/'inputs'/f'{split}_{rep:02d}.json';write(p,data);files[str(p)]=sha(p);inputs.append(dict(split=split,rep=rep,path=str(p)))
 write(OUT/'historical.json',dict(consumed_hashes=sorted(used),source_files=bindings));write(OUT/'generation_log.json',attempts)
 for name in ('historical.json','generation_log.json','fixture_passed.json','method_freeze.json'):files[str(OUT/name)]=sha(OUT/name)
 write(OUT/'registration.json',dict(files=files,inputs=inputs,seeds=SEEDS,api=0,episode_cap=3060,successful_final_fixture_episodes=12,preserved_earlier_fixture_episodes=12,total_pre_registration_episodes=24,optimizer_evaluations_cap=13,created=time.time()))
 package=ROOT/'docs/artifacts/sundial_cost_adapter_preregistration_v1';package.mkdir();entries={};key=credentials()
 paths=list(HERE.glob('*.py'))+[r.SPEC,r.PLAN,OUT/'registration.json',OUT/'method_freeze.json',OUT/'generation_log.json',OUT/'historical.json',OUT/'fixture_passed.json']+list((OUT/'inputs').glob('*.json'))
 paths += [p for p in (OUT/'fixture').rglob('*') if p.is_file()]+list((OUT/'logs').glob('*.log'))
 paths += [OUT/'pre_registration_diagnostics.json',OUT/'cache_hashes.json']
 for i,p in enumerate(paths):
  raw=p.read_bytes();assert not key or key not in raw
  dest=package/f'{i:03d}.gz';dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=sha(p),gzip_sha256=sha(dest))
 write(package/'manifest.json',dict(files=entries,lossless=True,credential_absent=True,api=0))
 write(OUT/'publication.json',dict(files={**{p:v['gzip_sha256'] for p,v in entries.items()},(package/'manifest.json').relative_to(ROOT).as_posix():sha(package/'manifest.json')}))
 print('COST_ADAPTER_REGISTERED',len(inputs),len(entries),flush=True)
def verify():
 v=read(OUT/'registration.json')
 for p,h in v['files'].items():assert sha(Path(p))==h,p
 return v
def published():
 v=verify();head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert head==remote
 for p,h in read(OUT/'publication.json')['files'].items():assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==h
 return v,head
def run():
 registration,head=published()
 with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),revision=head,api=0));completed=[];cache={};evaluations=[]
 def evaluation(split,parameters,methods=('cost_sundial',)):
  token=json.dumps([split,parameters,methods]);tag=hashlib.sha256(token.encode()).hexdigest()[:12]
  if token in cache:return cache[token]
  verify();rows=[]
  for item in [x for x in registration['inputs'] if x['split']==split]:
   for seed in SEEDS:
    label=f'{split}_{tag}_r{item["rep"]:02d}_s{seed}'
    write(OUT/'progress.json',dict(status='running',stage=split,task=label,parameters=parameters,completed_tasks=len(completed),api=0))
    local=execute(label,Path(item['path']),seed,parameters,methods,OUT/'runs')
    rows.extend([dict(x,seed=seed,rep=item['rep']) for x in local]);completed.append(label)
    write(OUT/'task_index.json',completed);verify()
  means={m:sum(x['cost'] for x in rows if x['method']==m and x['scenario']=='shock')/sum(x['method']==m and x['scenario']=='shock' for x in rows) for m in methods}
  result=dict(parameters=parameters,split=split,means=means,rows=rows)
  write(OUT/'evaluations'/f'{tag}.json',result);evaluations.append(dict(tag=tag,split=split,parameters=parameters,means=means));write(OUT/'evaluation_index.json',evaluations);cache[token]=result;return result
 try:
  current=[0.,0.,1.];best=evaluation('train',current)['means']['cost_sundial'];checkpoints=[current.copy()];search=[]
  for round_index,steps in enumerate(((1.,.5,.25),(.5,.25,.125))):
   for coordinate,step in enumerate(steps):
    center=current.copy();options=[]
    for direction in (-1,1):
     p=center.copy();p[coordinate]=float(min((2.,1.,1.5)[coordinate],max((-2.,0.,.5)[coordinate],p[coordinate]+direction*step)))
     value=evaluation('train',p)['means']['cost_sundial'];options.append(dict(parameters=p,cost=value))
    for option in options:
     if option['cost']<best:best=option['cost'];current=option['parameters'].copy()
    search.append(dict(round=round_index+1,coordinate=coordinate,starting=center,options=options,selected=current.copy(),cost=best));write(OUT/'search.json',search)
   checkpoints.append(current.copy());write(OUT/'checkpoints.json',checkpoints)
  dev=[evaluation('dev',p) for p in checkpoints];selected=min(range(3),key=lambda i:dev[i]['means']['cost_sundial']);parameters=checkpoints[selected]
  selection=dict(parameters=parameters,checkpoint=selected,dev_costs=[x['means']['cost_sundial'] for x in dev],selected_before_holdout=True)
  write(OUT/'selection.json',selection);selection_hash=sha(OUT/'selection.json')
  held=evaluation('holdout',parameters,('old_sundial','cost_sundial','original_merton'));assert sha(OUT/'selection.json')==selection_hash
  rows=[x for x in held['rows'] if x['scenario']=='shock'];means=held['means']
  service=lambda method,kind=None:sum(x['internal_service'] for x in rows if x['method']==method and (kind is None or x['type']==kind))/sum(x['method']==method and (kind is None or x['type']==kind) for x in rows)
  cost=lambda method,kind:sum(x['cost'] for x in rows if x['method']==method and x['type']==kind)/sum(x['method']==method and x['type']==kind for x in rows)
  checks=dict(cost_below_old=means['cost_sundial']<means['old_sundial'],cost_below_merton=means['cost_sundial']<means['original_merton'],internal_constraint=service('cost_sundial')<=service('old_sundial'),no_joint_category_degradation=all(not(cost('cost_sundial',k)>cost('old_sundial',k) and service('cost_sundial',k)>service('old_sundial',k)) for k in KINDS))
  episodes=sum(read(OUT/'runs'/label/'completed.json')['episodes'] for label in completed);assert episodes<=3060
  verify();write(OUT/'summary.json',dict(selection=selection,means=means,checks=checks,gate_passed=all(checks.values()),holdout_rows=held['rows'],api=0))
  write(OUT/'completed.json',dict(tasks=len(completed),episodes=episodes,rows=episodes*600,api=0,gate_passed=all(checks.values()),no_automatic_llm_run=True));write(OUT/'progress.json',dict(status='completed',gate_passed=all(checks.values()),api=0))
 except Exception as e:
  write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),preserved=True,completed_tasks=len(completed),api=0));traceback.print_exc();raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('fixture','register','verify','run'));a=p.parse_args();{'fixture':fixture,'register':register,'verify':verify,'run':run}[a.action]()
