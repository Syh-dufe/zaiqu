"""Independent cost and exact allocation audit against frozen random reference."""
import csv,json,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
def reference(seed,trace):
 if trace in (0,1):return ROOT/f'results/sundial_deterministic_remaining/v1/runs/seed{seed}_trace{trace}'
 if trace==3:return ROOT/f'results/sundial_deterministic_drop/v1/runs/seed{seed}_drop'
 return ROOT/f'results/{"sundial_deterministic_extension" if seed<=13 else "sundial_deterministic_cost"}/v1/runs/seed{seed}_double'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def audit(runner,directory,seed,trace,data):
 done=read(directory/'completed.json');assert done['episodes']==2 and done['rows']==1200 and done['calls']==0 and not done['runtime_failures']
 assert read(directory/'calls.json')==[] and read(directory/'forecast_model_checks.json')['unchanged']
 assert all(x['unchanged'] for x in done['parameter_checks'].values())
 old=reference(seed,trace);assert read(old/'independent_audit.json')['status']=='passed'
 with (old/'periods.csv').open(encoding='utf-8',newline='') as f:ref={(x['scenario'],x['period'],x['node']):x for x in csv.DictReader(f) if x['group']=='adapted_sundial'}
 with (directory/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
 assert len(rows)==1200 and len({tuple(x[k] for k in ('group','scenario','trace','period','node')) for x in rows})==1200
 for x in rows:
  assert x['group']=='adapted_sundial' and int(x['trace'])==trace
  assert float(x['cost'])==int(x['inventory'])+int(x['backlog']) and 0<=int(x['actual_order'])<=20
  assert int(x['demand'])==data['base' if x['scenario']=='base' else 'shock'][trace][int(x['period'])-1]
  if x['scenario']=='base' or int(x['period'])<data['events'][trace]['start_index']+3:
   y=ref[x['scenario'],x['period'],x['node']];assert all(x[k]==y[k] for k in ('cost','inventory','backlog','actual_order','policy_order','demand'))
   assert x['chosen']=='zero' and x['actual_order']==x['policy_order']
 for info in read(directory/'information_audits.json'):assert info['delivered_through_period']<=info['observed_periods']==info['decision_period']-1
 old_scores={s['decision_period']:s for s in read(old/'scores.json') if s['group']=='adapted_sundial' and s['scenario']=='shock'}
 checked=0
 for s in read(directory/'scores.json'):
  assert s['no_llm'] and s['trace']==trace
  if s.get('generation_event'):
   a=s['candidate_construction'];assert a['initial_score_calls']<=27 and a['refinement_score_calls']==6
  v=s['forecast_audit'];p=v['prediction'];prior=old_scores[s['decision_period']]['forecast_audit']['prediction']
  assert p['raw_blocks']==prior['raw_blocks'] and p['selected_blocks']==prior['selected_blocks']
  assert p['sampling_seeds']==prior['sampling_seeds'] and p['original_random_paths']==prior['diagnostic_paths']
  assert p['allocation_variant']=='balanced_rotating_remainder' and p['actual_variant']=='multiscale24_balanced'
  h=min(20,201-s['decision_period']);age=v['report_age'];expected=[];totals=[]
  for draw,blockrow in enumerate(p['selected_blocks']):
   sequence=[];ks=[]
   for j,m in enumerate(blockrow):
    k=math.floor(3*min(20,max(0,m))+.5);q,r=divmod(k,3);start=(j+draw)%3
    slots=[q+int((slot-start)%3<r) for slot in range(3)]
    assert sum(slots)==k and max(slots)-min(slots)<=1 and all(0<=z<=20 for z in slots)
    sequence.extend(slots);ks.append(k)
   expected.append(sequence[age:age+h]);totals.append(ks)
  assert len(expected)==32 and expected==p['diagnostic_paths'] and totals==p['allocation_totals']==prior['allocation_totals']
  assert list(s['forecasts'][0])+list(s['forecasts'][1])==[expected[i] for i in (0,1,2,16,17,18)]
  checked+=1
 summary=[]
 for e in read(directory/'episodes.json'):
  costs=[float(x['cost']) for x in rows if x['scenario']==e['scenario']];assert len(costs)==600 and abs(sum(costs)/600-e['cost'])<1e-10 and e['episode_http']==0
  summary.append(dict(seed=seed,trace=trace,type=data['events'][trace]['type'],scenario=e['scenario'],method='multiscale24_balanced',cost=sum(costs)/600))
 runner.core.write(directory/'independent_audit.json',dict(status='passed',rows=1200,api=0,checked_forecasts=checked,old_blocks_exact=True,totals_exact=True,balance_and_crop_exact=True,all_models_unchanged=True,normal_pre_notice_exact=True,cost_recomputed=True))
 return summary
