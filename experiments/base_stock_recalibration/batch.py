"""Fresh demand development of the standard H40 Base-stock; no API or result filtering."""
import argparse,csv,gzip,hashlib,importlib.util,json,os,socket,subprocess,sys,time,traceback
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=ROOT/'results/base_stock_recalibration/v1'
SPEC=ROOT/'docs/superpowers/specs/2026-10-16-base-stock-recalibration-design.md'
PLAN=ROOT/'docs/superpowers/plans/2026-10-16-base-stock-recalibration.md'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
reuse=module('recalibration_frozen_reference',ROOT/'experiments/sundial_fixed_base_stock_recovery/batch.py')
old=reuse.base;read=old.read;write=old.write;sha=old.sha;KINDS=old.KINDS
def trace_hash(x):return hashlib.sha256(json.dumps(list(map(int,x[:200])),separators=(',',':')).encode()).hexdigest()
def walk(v,used):
 if isinstance(v,dict):
  if isinstance(v.get('consumed_hashes'),list):used.update(v['consumed_hashes'])
  for k,item in v.items():
   if k in ('base','shock') and isinstance(item,list):
    seqs=[item] if len(item)>=200 and all(isinstance(x,(int,float)) for x in item[:200]) else item
    for x in seqs:
     if isinstance(x,list) and len(x)>=200 and all(isinstance(y,(int,float)) and np.isfinite(y) for y in x[:200]):used.add(trace_hash(x))
   elif isinstance(item,(dict,list)):walk(item,used)
 elif isinstance(v,list):
  for x in v:
   if isinstance(x,(dict,list)):walk(x,used)
def profile(base,kind,offset):
 import math
 bounds={'single_surge':[(80+offset,100+offset,1.5)],'sustained_surge':[(70+offset,120+offset,1.25)],'double_surge':[(75+offset,95+offset,1.5),(115+offset,135+offset,1.5)]}[kind]
 shock=base.copy()
 for a,b,k in bounds:
  for j in range(a,b):shock[j]=min(20,math.ceil(k*base[j]))
 return shock,dict(type=kind,start_index=bounds[0][0],intervals=[dict(start=a,end=b,factor=k) for a,b,k in bounds])
def verify():
 r=read(OUT/'registration.json')
 for p,h in r['files'].items():assert sha(p)==h,p
 return r
def register():
 assert not OUT.exists();OUT.mkdir(parents=True)
 files=dict(read(old.OUT/'registration.json')['files'])
 for p in [*HERE.glob('*.py'),SPEC,PLAN,ROOT/'docs/2026-10-16-liu-base-stock-protocol-check.md']:
  files[str(p)]=sha(p)
 for p in old.OUT.rglob('*'):
  if p.is_file():files[str(p)]=sha(p)
 write(OUT/'method_freeze.json',dict(files=files,H=40,L=4,z_candidates=list(range(20)),created=time.time(),api=0))
 used=set();bindings=[]
 for parent in (ROOT/'results',ROOT/'docs/artifacts'):
  for p in parent.rglob('*.json'):
   if OUT in p.parents or not any(w in p.name.lower() for w in ('input','demand','historical')):continue
   try:v=read(p)
   except (OSError,ValueError):continue
   before=len(used);walk(v,used)
   if len(used)!=before:bindings.append(dict(path=str(p),sha256=sha(p)))
 sys.path.insert(0,str(old.bs.AUTHOR));from envs.generator import merton
 for p in (old.bs.AUTHOR/'test_data/test_demand_merton').glob('*.txt'):used.add(trace_hash(np.loadtxt(p).reshape(-1)));bindings.append(dict(path=str(p),sha256=sha(p)))
 historical_count=len(used);attempts=[];inputs=[];candidate=20274001
 for split,count in (('development',8),('holdout',10)):
  for batch in range(count):
   data=dict(base=[],shock=[],events=[],split=split,batch=batch,seed_records=[])
   for kind in KINDS:
    while True:
     assert candidate<=20274999
     seed=candidate;candidate+=1;np.random.seed(seed);base=list(map(int,merton(200,20).demand_list));shock,event=profile(base,kind,-10+2*batch)
     hashes={trace_hash(base),trace_hash(shock)};collision=bool(hashes&used)
     attempts.append(dict(seed=seed,split=split,batch=batch,type=kind,collision=collision,zero_actual_shock=base==shock))
     if not collision:used.update(hashes);break
    data['base'].append(base);data['shock'].append(shock);data['events'].append(event);data['seed_records'].append(seed)
   p=OUT/'inputs'/f'{split}_{batch:02d}.json';write(p,data);files[str(p)]=sha(p);inputs.append(dict(split=split,batch=batch,path=str(p)))
 write(OUT/'historical.json',dict(historical_trace_count=historical_count,consumed_hashes=sorted(used),source_files=bindings))
 write(OUT/'generation_log.json',attempts)
 for name in ('method_freeze.json','historical.json','generation_log.json'):files[str(OUT/name)]=sha(OUT/name)
 write(OUT/'registration.json',dict(files=files,inputs=inputs,H=40,L=4,z_candidates=list(range(20)),development_paths=24,holdout_paths=30,episode_cap=1152,node_period_cap=691200,api=0,selection='minimum equal-type development shock cost; exact tie smaller z',old_z2_fixed_root=str(old.OUT)))
 public=reuse.archive(ROOT/'docs/artifacts/base_stock_recalibration_preregistration_v1',[*HERE.glob('*.py'),SPEC,PLAN,ROOT/'docs/2026-10-16-liu-base-stock-protocol-check.md',OUT/'registration.json',OUT/'method_freeze.json',OUT/'historical.json',OUT/'generation_log.json']+list((OUT/'inputs').glob('*.json')))
 write(OUT/'publication.json',dict(files=public));print('BASE_STOCK_RECALIBRATION_REGISTERED',len(inputs),'batches',len(attempts),'candidates',flush=True)
def published():
 r=verify();head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert head==remote
 old.check_publication(OUT/'publication.json');return r,head
def evaluate(input_record,z,stage):
 data=read(Path(input_record['path']));batch=input_record['batch'];folder=OUT/'runs'/stage/f'z{z:02d}'/f'batch{batch:02d}';folder.mkdir(parents=True,exist_ok=False)
 scores=[];base_rows={};config=dict(name=f'z{z:02d}',z=z,information='local',rounding='ceil')
 with gzip.open(folder/'periods.csv.gz','wt',encoding='utf-8',newline='') as f:
  writer=None
  for trace,kind in enumerate(KINDS):
   for scenario in ('base','shock'):
    result=old.bs.episode(data[scenario][trace],z=z,information='local',rounding='ceil');rows=result.pop('rows')
    audited=old.numerical.verify_episode(rows,data[scenario][trace],config);assert abs(audited-result['cost'])<1e-10 and result['ledger_verified']
    if scenario=='base':base_rows[trace]=rows
    else:
     for x,y in zip(base_rows[trace],rows):
      if int(y['period'])>=data['events'][trace]['start_index']:break
      assert all(x[k]==y[k] for k in ('inventory','backlog','action','cost','target','position','demand','after_unshipped'))
    identity=dict(stage=stage,z=z,batch=batch,trace=trace,type=kind,scenario=scenario)
    for row in rows:
     value=dict(**identity,**row)
     if writer is None:writer=csv.DictWriter(f,fieldnames=list(value));writer.writeheader()
     writer.writerow(value)
    scores.append(dict(**identity,**result))
 write(folder/'episodes.json',scores);write(folder/'completed.json',dict(episodes=6,rows=3600,api=0,scalar_audit=True,normal_prefix=True,input_sha256=sha(Path(input_record['path']))));return scores
def shock_mean(rows):return sum(x['cost'] for x in rows if x['scenario']=='shock')/sum(x['scenario']=='shock' for x in rows)
def run():
 registration,head=published()
 with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),revision=head,api=0));started=time.perf_counter();scores=[];dev=[];done=0
 def forbidden(*a,**kw):raise RuntimeError('Network forbidden in registered local Base-stock experiment')
 socket.socket.connect=forbidden;socket.create_connection=forbidden
 try:
  for z in registration['z_candidates']:
   current=[]
   for entry in [x for x in registration['inputs'] if x['split']=='development']:
    verify();write(OUT/'progress.json',dict(status='running',stage='development',z=z,batch=entry['batch'],completed_episodes=done,api=0))
    local=evaluate(entry,z,'development');current.extend(local);scores.extend(local);done+=6
   dev.append(dict(z=z,shock_cost=shock_mean(current),normal_cost=sum(x['cost'] for x in current if x['scenario']=='base')/24));write(OUT/'development_scan.json',dev);write(OUT/'episodes.json',scores)
  chosen=min(dev,key=lambda x:(x['shock_cost'],x['z']))['z']
  selection=dict(selected_z=chosen,H=40,L=4,selected_before_holdout=True,selection_data='development_only',candidates=dev)
  write(OUT/'selection.json',selection);selection_sha=sha(OUT/'selection.json');configs=sorted({chosen,8,2});hold=[]
  for z in configs:
   for entry in [x for x in registration['inputs'] if x['split']=='holdout']:
    verify();assert sha(OUT/'selection.json')==selection_sha
    write(OUT/'progress.json',dict(status='running',stage='holdout',selected_z=chosen,z=z,batch=entry['batch'],completed_episodes=done,api=0))
    local=evaluate(entry,z,'holdout');hold.extend(local);scores.extend(local);done+=6;write(OUT/'episodes.json',scores)
  fixed=[];old_fixed=read(old.OUT/'episodes.json')
  for z in configs:
   if z==2:
    fixed.extend(dict(x,z=2,stage='fixed',reused=True) for x in old_fixed)
   else:
    entry=dict(path=str(old.INPUT),batch=0);local=evaluate(entry,z,'fixed');fixed.extend(local);scores.extend(local);done+=6
  rows=[]
  for kind in KINDS:
   old_line=next(x for x in read(old.OUT/'summary.json')['by_type'] if x['type']==kind)
   costs={str(z):next(x['cost'] for x in fixed if x['z']==z and x['type']==kind and x['scenario']=='shock') for z in configs}
   rows.append(dict(type=kind,happo=old_line['happo'],full_merton=old_line['full_merton'],full_sundial=old_line['full_sundial'],base_stock_selected=costs[str(chosen)],base_stock_reference8=costs['8'],base_stock_historical2=costs['2']))
  summary=dict(selected_z=chosen,development_scan=dev,holdout={str(z):dict(shock_cost=shock_mean([x for x in hold if x['z']==z]),by_type={k:shock_mean([x for x in hold if x['z']==z and x['type']==k]) for k in KINDS}) for z in configs},fixed_by_type=rows,fixed_overall={k:sum(x[k] for x in rows)/3 for k in ('happo','full_merton','full_sundial','base_stock_selected','base_stock_reference8','base_stock_historical2')},api=0,new_episodes=done,normal_and_unfavorable_retained=True,all_candidates_preserved=True,holdout_has_no_llm_results=True)
  assert done<=1152 and sha(OUT/'selection.json')==selection_sha
  verify();write(OUT/'episodes.json',scores);write(OUT/'fixed_episodes_including_reused.json',fixed);write(OUT/'numerical_boundaries.json',old.numerical.BOUNDARIES);write(OUT/'summary.json',summary)
  write(OUT/'completed.json',dict(episodes=done,rows=done*600,api=0,selected_z=chosen,selection_sha256=selection_sha,seconds=time.perf_counter()-started,all_scalar_audits=True));write(OUT/'progress.json',dict(status='completed',episodes=done,selected_z=chosen,api=0))
  public=reuse.archive(ROOT/'docs/artifacts/base_stock_recalibration_completed_v1',[p for p in OUT.rglob('*') if p.is_file()]+list(HERE.glob('*.py'))+[SPEC,PLAN])
  write(OUT/'completed_publication.json',dict(files=public));print('BASE_STOCK_RECALIBRATION_COMPLETED',chosen,summary['fixed_overall'],flush=True)
 except Exception as e:write(OUT/'failed.json',dict(error=type(e).__name__,detail=str(e),completed_episodes=done,preserved=True,api=0));traceback.print_exc();raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run','verify','check-publication'));a=p.parse_args()
 {'register':register,'run':run,'verify':verify,'check-publication':lambda:old.check_publication(OUT/'completed_publication.json')}[a.action]()
