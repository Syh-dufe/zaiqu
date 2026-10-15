"""Independent costs, causal inputs, frozen weights and forecast arithmetic."""
import csv,json,hashlib
import numpy as np
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def audit(r,directory,data,methods,parameters):
 done=read(directory/'completed.json');n=len(methods)*6
 assert done['episodes']==n and done['rows']==n*600 and done['calls']==0 and not done['runtime_failures']
 assert read(directory/'calls.json')==[] and read(directory/'forecast_model_checks.json')['unchanged']
 assert all(v['unchanged'] for v in done['parameter_checks'].values())
 with (directory/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
 assert len(rows)==n*600 and len({tuple(x[k] for k in ('group','scenario','trace','period','node')) for x in rows})==len(rows)
 index={(x['group'],x['scenario'],x['trace'],x['period'],x['node']):x for x in rows}
 for x in rows:
  t=int(x['trace']);p=int(x['period']);assert float(x['cost'])==int(x['inventory'])+int(x['backlog'])
  assert 0<=int(x['actual_order'])<=20 and int(x['demand'])==data['base' if x['scenario']=='base' else 'shock'][t][p-1]
  if x['scenario']=='base' or p<data['events'][t]['start_index']+3:assert x['chosen']=='zero' and x['actual_order']==x['policy_order']
  if x['scenario']=='shock' and p<=data['events'][t]['start_index']:
   y=index[x['group'],'base',x['trace'],x['period'],x['node']]
   assert all(x[k]==y[k] for k in ('cost','actual_order','inventory','backlog','policy_order','demand'))
 for i in read(directory/'information_audits.json'):
  assert i['delivered_through_period']<=i['observed_periods']==i['decision_period']-1
 count=0
 for s in read(directory/'scores.json'):
  assert s['no_llm'] and s['scenario']=='shock'
  if s.get('generation_event'):
   c=s['candidate_construction'];assert c['initial_score_calls']<=27 and c['refinement_score_calls']==6
  v=s['forecast_audit'];assert v['provider']==s['group']
  assert v['delivered_through']==v['decision_period']-1-v['report_age']
  if s['group']=='original_merton':continue
  p=v['prediction'];raw=np.clip(np.asarray(p['raw_blocks'],dtype=np.float64),0,20);history=p['block_history'];age=v['report_age']
  base=r.response.base.correction.transform(raw,r.response.base.correction.features(history,raw,age),read(r.response.ADAPTER)['weights'])
  assert np.array_equal(base,np.asarray(p['base_selected_blocks']))
  shifted=np.clip(base+np.clip(.5*3/(3+age)*(history[-1]-base.mean(0)),-4,4)[None,:],0,20)
  assert np.array_equal(shifted,np.asarray(p['cost_base_blocks']))
  params=parameters if s['group']=='cost_sundial' else [0.,0.,1.]
  assert p['cost_parameters']==params
  b,z,a=params;mu=shifted.mean(0);d=np.clip(history[-1]-history[-2],-4,4) if len(history)>1 else 0.
  expected=shifted.copy() if params==[0.,0.,1.] else np.clip(mu[None,:]+b+z*d*np.exp(-(age+3*np.arange(shifted.shape[1]))/6)[None,:]+a*(shifted-mu[None,:]),0,20)
  assert np.array_equal(expected,np.asarray(p['cost_blocks']))
  value=r.response.base.allocate(expected,age,v['horizon'],v['stream_identity'])
  assert value['paths']==p['cost_paths'] and value['totals']==p['cost_allocation_totals']
  assert list(s['forecasts'][0])+list(s['forecasts'][1])==value['deployment']
  count+=1
 result=[]
 for e in read(directory/'episodes.json'):
  local=[x for x in rows if x['group']==e['group'] and x['scenario']==e['scenario'] and int(x['trace'])==e['trace']]
  cost=sum(float(x['cost']) for x in local)/600
  assert len(local)==600 and abs(cost-e['cost'])<1e-10 and e['episode_http']==0
  service=sum(int(x['backlog']) for x in local if x['node']=='0')/200
  result.append(dict(method=e['group'],scenario=e['scenario'],trace=e['trace'],type=data['events'][e['trace']]['type'],cost=cost,internal_service=service))
 if len(methods)==2 and parameters==[0.,0.,1.]:
  for x in rows:
   y=index[methods[0],x['scenario'],x['trace'],x['period'],x['node']]
   assert all(x[k]==y[k] for k in ('cost','actual_order','inventory','backlog','policy_order'))
 r.core.write(directory/'independent_audit.json',dict(status='passed',episodes=n,rows=n*600,api=0,forecast_checks=count,cost_recomputed=True,causal_prefix=True,parameters_unchanged=True))
 return result
