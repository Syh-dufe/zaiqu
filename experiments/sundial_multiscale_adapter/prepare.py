"""Whole-path isolation, history collision exclusion and causal k3 windows."""
import math
import numpy as np
from common import ROOT,OUT,module,read,write,digest,trace_hash,verify
BACKGROUNDS=('stationary','trend','periodic')
TYPES=('normal','single_surge','sustained_surge','double_surge','surge_then_drop')
def prepare():
 verify();used=set();bindings=[]
 def walk(value):
  found=[]
  if isinstance(value,dict):
   if isinstance(value.get('consumed_hashes'),list):used.update(value['consumed_hashes'])
   for key,item in value.items():
    if key in ('base','shock') and isinstance(item,list):
     sequences=[item] if len(item)>=200 and all(isinstance(v,(int,float)) for v in item[:200]) else item
     for trace in sequences:
      if isinstance(trace,list) and len(trace)>=200 and all(isinstance(v,(int,float)) and math.isfinite(v) for v in trace[:200]):found.append(trace_hash(trace))
    elif isinstance(item,(dict,list)):found.extend(walk(item))
  elif isinstance(value,list):
   for item in value:
    if isinstance(item,(dict,list)):found.extend(walk(item))
  return found
 for parent in (ROOT/'results',ROOT/'docs/artifacts'):
  for path in parent.rglob('*.json'):
   if OUT in path.parents or not any(word in path.name.lower() for word in ('input','demand','historical')):continue
   try:value=read(path)
   except (OSError,ValueError):continue
   before=len(used);found=walk(value)
   if found or len(used)!=before:used.update(found);bindings.append(dict(path=str(path),sha256=digest(path),traces=len(found)))
 normal=sorted((ROOT/'external/liu-inventory/test_data/test_demand_merton').glob('*.txt'));assert len(normal)==20
 for path in normal:used.add(trace_hash(np.loadtxt(path).reshape(-1)));bindings.append(dict(path=str(path),sha256=digest(path),traces=1))
 write(OUT/'historical.json',dict(consumed_hashes=sorted(used),source_files=bindings))
 generator=module('multiscale_profile_generator',ROOT/'experiments/joint_baseline_confirmation/batch.py')
 reports=module('multiscale_k3_reports',ROOT/'experiments/deepseek_refinement/reports.py')
 inputs=[];cases=[];attempts=[];seed=20272201;new=set()
 for split,count in (('train',8),('dev',2)):
  for background in BACKGROUNDS:
   for kind in TYPES:
    for repetition in range(count):
     offset=-10+2*repetition
     while True:
      candidate=seed;seed+=1;rng=np.random.default_rng(candidate);t=np.arange(200)
      mean=np.full(200,10.) if background=='stationary' else 6+8*t/199 if background=='trend' else 10+4*np.sin(2*np.pi*t/40)
      base=np.clip(rng.poisson(mean),0,20).astype(int).tolist()
      shock,event=(base.copy(),dict(type='normal',start_index=80+offset,intervals=[])) if kind=='normal' else generator.profile_trace(base,kind,offset)
      hashes={trace_hash(base),trace_hash(shock)};collision=bool(hashes&(used|new));attempts.append(dict(seed=candidate,split=split,background=background,type=kind,collision=collision))
      if not collision:break
      assert seed<20273201,'Candidate cap exceeded'
     new.update(hashes);pid=f'{split}_{background}_{kind}_{repetition+1}'
     inputs.append(dict(path_id=pid,split=split,background=background,type=kind,seed=candidate,base=[base],shock=[shock],event=event))
     for offset_window in (-9,3,13,33,53,73):
      decision=event['start_index']+offset_window;assert 1<=decision<=181
      r=reports.DemandReports(3)
      for i,value in enumerate(shock[:decision-1],1):r.observe(value,i)
      blocks=[d['demand_mean'] for d in r.deliveries];assert len(blocks)*3+r.age==decision-1
      future=shock[decision-1:decision+19];assert len(future)==20
      cases.append(dict(id=f'{pid}_o{offset_window}',path_id=pid,split=split,background=background,type=kind,decision_period=decision,report_age=r.age,block_history=blocks,future_label=future))
 assert len(inputs)==150 and len(cases)==900
 assert len({trace_hash(p['shock'][0]) for p in inputs})==150
 train={trace_hash(p['shock'][0]) for p in inputs if p['split']=='train'};dev={trace_hash(p['shock'][0]) for p in inputs if p['split']=='dev'};assert not train&dev
 write(OUT/'inputs.json',inputs);write(OUT/'cases.json',cases);write(OUT/'generation_log.json',attempts)
 write(OUT/'prepared.json',dict(train_paths=120,dev_paths=30,windows=900,historical_traces=len(used),input_sha256=digest(OUT/'inputs.json'),case_sha256=digest(OUT/'cases.json'),all_collisions_excluded=True))
 verify();print('MULTISCALE_INPUTS_PREPARED',150,900,flush=True)
