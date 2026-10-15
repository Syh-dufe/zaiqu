"""Independent causal response reconstruction and full cost audit."""
import csv,json
import numpy as np
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def audit(runner,directory,seed,candidate,data):
 done=read(directory/'completed.json');assert done['episodes']==8 and done['rows']==4800 and done['calls']==0 and not done['runtime_failures']
 assert read(directory/'calls.json')==[] and read(directory/'forecast_model_checks.json')['unchanged'] and all(v['unchanged'] for v in done['parameter_checks'].values())
 with (directory/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
 assert len(rows)==4800 and len({tuple(x[k] for k in ('group','scenario','trace','period','node')) for x in rows})==4800
 bykey={(x['scenario'],x['trace'],x['period'],x['node']):x for x in rows}
 for x in rows:
  trace=int(x['trace']);period=int(x['period']);assert x['group']=='adapted_sundial' and float(x['cost'])==int(x['inventory'])+int(x['backlog']) and 0<=int(x['actual_order'])<=20
  assert int(x['demand'])==data['base' if x['scenario']=='base' else 'shock'][trace][period-1]
  if x['scenario']=='base' or period<data['events'][trace]['start_index']+3:assert x['chosen']=='zero' and x['actual_order']==x['policy_order']
  if x['scenario']=='shock' and period<=data['events'][trace]['start_index']:
   y=bykey['base',x['trace'],x['period'],x['node']];assert all(x[k]==y[k] for k in ('cost','actual_order','inventory','backlog','policy_order','demand'))
 information=read(directory/'information_audits.json')
 for i in information:assert i['delivered_through_period']<=i['observed_periods']==i['decision_period']-1
 checked=0;coefbank={'zero':(0,0,0),'all_half':(.5,.5,.5),'up_half':(.5,0,0),'down_half':(0,.5,0),'change_half':(.5,.5,0)}
 for s in read(directory/'scores.json'):
  assert s['no_llm'] and s['scenario']=='shock'
  if s.get('generation_event'):
   c=s['candidate_construction'];assert c['initial_score_calls']<=27 and c['refinement_score_calls']==6
  v=s['forecast_audit'];p=v['prediction'];b=np.asarray(p['block_history'],dtype=float);base=np.asarray(p['base_selected_blocks'],dtype=np.float64)
  raw=np.clip(np.asarray(p['raw_blocks'],dtype=np.float64),0,20);f=runner.predictor.base.correction.features(b.tolist(),raw,v['report_age']);weights=read(runner.predictor.ADAPTER)['weights']
  expected_base=runner.predictor.base.correction.transform(raw,f,weights);assert np.array_equal(base,expected_base)
  previous=b[max(0,len(b)-11):-1];z=float((b[-1]-np.mean(b[-4:-1]))/max(1.,float(np.std(previous)))) if len(b)>=4 else 0.
  state='up' if z>.5 else 'down' if z<-.5 else 'flat';coefficient=coefbank[candidate][{'up':0,'down':1,'flat':2}[state]]*3/(3+v['report_age'])
  shift=np.minimum(4,np.maximum(-4,coefficient*(float(b[-1])-np.mean(base,axis=0))));selected=np.clip(base+shift[None,:],0,20)
  response=p['response'];assert response['state']==state and response['z']==z and response['coefficient']==coefficient and response['candidate']==candidate
  assert np.array_equal(selected,np.asarray(p['selected_blocks'])) and np.array_equal(shift,np.asarray(response['block_shifts']))
  allocated=runner.predictor.base.allocate(selected,v['report_age'],v['horizon'],v['stream_identity'])
  assert allocated['paths']==p['diagnostic_paths'] and allocated['totals']==p['allocation_totals'] and allocated['allocation_seeds']==p['allocation_seeds']
  assert list(s['forecasts'][0])+list(s['forecasts'][1])==allocated['deployment']
  if candidate=='zero':assert p['base_random_paths']==allocated['paths']
  checked+=1
 summary=[]
 for e in read(directory/'episodes.json'):
  costs=[float(x['cost']) for x in rows if x['scenario']==e['scenario'] and int(x['trace'])==e['trace']];assert len(costs)==600 and abs(sum(costs)/600-e['cost'])<1e-10 and e['episode_http']==0
  summary.append(dict(seed=seed,candidate=candidate,trace=e['trace'],type=data['events'][e['trace']]['type'],scenario=e['scenario'],cost=sum(costs)/600))
 runner.core.write(directory/'independent_audit.json',dict(status='passed',rows=4800,api=0,checked_forecasts=checked,response_recomputed=True,original_adapter_exact=True,allocation_recomputed=True,all_models_unchanged=True,cost_recomputed=True,normal_pre_notice_zero_proposal=True))
 return summary
