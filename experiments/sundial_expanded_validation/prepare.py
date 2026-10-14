"""Freeze methods before new input generation; no score-based selection."""
import sys
import numpy as np
from common import ROOT,HERE,OUT,read,write,digest,module,pilot

def prepare():
 assert not OUT.exists(),'Preserve previous validation'
 prior=read(ROOT/'results/sundial_forecast_pilot/development_v1/freeze.json')
 for p,sha in prior['sha256'].items():assert digest(p)==sha,p
 generator=module('sundial_original_input_generator',ROOT/'experiments/joint_baseline_confirmation/batch.py')
 source=list(HERE.glob('*.py'))+[ROOT/'experiments/timesfm_path_development/paths.py',ROOT/'experiments/joint_baseline_confirmation/batch.py',ROOT/'external/liu-inventory/envs/generator.py',ROOT/'experiments/deepseek_refinement/reports.py',ROOT/'docs/superpowers/specs/2026-10-14-sundial-expanded-design.md',ROOT/'docs/superpowers/plans/2026-10-14-sundial-expanded.md']
 hashes=prior['sha256'].copy();hashes.update({str(p):digest(p) for p in source})
 OUT.mkdir(parents=True);write(OUT/'freeze.json',dict(sha256=hashes,model_revision=pilot.REVISION,api=0,training=0,methods_frozen_before_generation=True))
 try:
  history,bindings=generator.historical_traces(OUT)
  history_hashes=sorted(generator.trace_hash(t) for t in history)
  write(OUT/'historical_paths.json',dict(source_files=bindings,consumed_hashes=history_hashes))
  accepted=[];attempts=[];used=set(history)
  for candidate in range(20271701,20271751):
   batch=len(accepted)+1;data=generator.generated_batch(candidate,batch-1)
   records=generator.input_path_records(data);groups={}
   for trace,scenario,value in records:groups.setdefault(trace,set()).add(value)
   within=set();collision=False
   for trace,sequences in groups.items():
    if any(t in used or t in within for t in sequences):collision=True
    within.update(sequences)
   attempts.append(dict(seed=candidate,batch=batch,collision=collision))
   if collision:continue
   used.update(within);accepted.append(data)
   if len(accepted)==5:break
  assert len(accepted)==5
  write(OUT/'inputs.json',accepted);write(OUT/'generation_log.json',attempts)
  reports=module('sundial_causal_report_builder',ROOT/'experiments/deepseek_refinement/reports.py')
  cases=[]
  for b,data in enumerate(accepted,1):
   for trace,event in enumerate(data['events']):
    for offset in (0,5,10,15,25,40):
     p=event['start_index']+3+offset;r=reports.DemandReports(3)
     for index,value in enumerate(data['shock'][trace][:p-1],1):r.observe(value,index)
     blocks=[item['demand_mean'] for item in r.deliveries]
     assert len(blocks)*3+r.age==p-1
     future=data['shock'][trace][p-1:p+19];assert len(future)==20
     cases.append(dict(id=f'new_b{b}_t{trace}_offset{offset}',path_id=f'b{b}_t{trace}',batch=b,trace=trace,type=event['type'],offset=offset,decision_period=p,report_age=r.age,block_history=blocks,future_label=future))
  assert len(cases)==120 and len({c['path_id'] for c in cases})==20
  write(OUT/'cases.json',cases)
  write(OUT/'prepared.json',dict(paths=20,cases=120,historical_paths=len(history),inputs_sha256=digest(OUT/'inputs.json'),cases_sha256=digest(OUT/'cases.json'),zero_actual_shock_pairs=sum(data['base'][t][:200]==data['shock'][t][:200] for data in accepted for t in range(4)),api=0,training=0))
  print('PREPARED_20_NEW_PATHS_120_CAUSAL_WINDOWS',flush=True)
 except Exception as exc:
  write(OUT/'prepare_failed.json',dict(error=type(exc).__name__,detail=str(exc),preserved=True));raise
if __name__=='__main__':prepare()
