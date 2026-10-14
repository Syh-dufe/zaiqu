import hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=ROOT/'results/sundial_adapter_development/v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
pilot=module('adapter_locked_sundial',ROOT/'experiments/sundial_forecast_pilot/run.py')
paths=module('adapter_locked_paths',ROOT/'experiments/timesfm_path_development/paths.py')
def verify_freeze():
 for p,sha in read(OUT/'freeze.json')['sha256'].items():assert digest(p)==sha,p
def trace_hash(t):return hashlib.sha256(json.dumps(list(t[:200]),separators=(',',':')).encode()).hexdigest()
def historical():
 prior=ROOT/'results/sundial_expanded_validation/v1';record=read(prior/'historical_paths.json');used=set(record['consumed_hashes'])
 for binding in record['source_files']:
  p=Path(binding['path']);p=p if p.is_absolute() else ROOT/p;assert digest(p)==binding['sha256'],p
 for data in read(prior/'inputs.json'):
  for scenario in ('base','shock'):
   used.update(trace_hash(t) for t in data[scenario])
 return used
def generate(split,count,start_seed,used):
 generator=module('adapter_registered_generator',ROOT/'experiments/joint_baseline_confirmation/batch.py');data=[];log=[]
 for seed in range(start_seed,start_seed+50):
  b=len(data);candidate=generator.generated_batch(seed,b);seen=set();collision=False
  for trace in range(4):
   pair={trace_hash(candidate[s][trace]) for s in ('base','shock')}
   if pair&used or pair&seen:collision=True
   seen.update(pair)
  log.append(dict(seed=seed,collision=collision))
  if collision:continue
  used.update(seen);data.append(candidate)
  if len(data)==count:break
 assert len(data)==count
 reports=module('adapter_causal_reports',ROOT/'experiments/deepseek_refinement/reports.py');cases=[]
 for batch,item in enumerate(data,1):
  for trace,event in enumerate(item['events']):
   for offset in (0,5,10,15,25,40):
    p=event['start_index']+3+offset;r=reports.DemandReports(3)
    for index,value in enumerate(item['shock'][trace][:p-1],1):r.observe(value,index)
    blocks=[d['demand_mean'] for d in r.deliveries];assert len(blocks)*3+r.age==p-1
    label=item['shock'][trace][p-1:p+19];assert len(label)==20
    cases.append(dict(id=f'{split}_b{batch}_t{trace}_o{offset}',path_id=f'{split}_b{batch}_t{trace}',batch=batch,trace=trace,type=event['type'],offset=offset,decision_period=p,report_age=r.age,block_history=blocks,future_label=label))
 write(OUT/f'{split}_inputs.json',data);write(OUT/f'{split}_cases.json',cases);write(OUT/f'{split}_generation_log.json',log)
 return cases
