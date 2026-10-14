"""Independent raw costs, true executed rules and period-allocation audit."""
import inspect,csv,json,hashlib,math
from pathlib import Path
import numpy as np

def independent_allocate(blocks,age,horizon,identity,seed_function):
 rows=[]
 for i,x in enumerate(blocks):
  purpose='search' if i<16 else 'review';rng=np.random.default_rng(seed_function(identity,f'allocate_{purpose}_{i%16}'))
  u=rng.random((len(x),60));periods=[]
  for j,m in enumerate(x):
   total=math.floor(3*max(0,min(20,float(m)))+.5);counts=np.zeros(3,dtype=int)
   for draw in range(total):
    available=np.flatnonzero(counts<20);k=min(len(available)-1,math.floor(u[j,draw]*len(available)));counts[available[k]]+=1
   assert counts.sum()==total;periods.extend(counts.tolist())
  rows.append(periods[age:age+horizon])
 return rows

def audit(runner,directory,data,expected_hash,offline=False):
 core=runner.core;directory=Path(directory);methods=runner.METHODS
 legacy=runner.module('sundial_explicit_raw_auditor',runner.ROOT/'experiments/submission_required/audit.py')
 text=inspect.getsource(legacy.audit);needle="('online_feedback','no_feedback','no_review','first_only')";assert text.count(needle)==1;text=text.replace(needle,repr(methods))
 needle="context=__import__('json').loads(content)";assert text.count(needle)==1;text=text.replace(needle,needle+";context=context.get('context',context)")
 ns=dict(legacy.__dict__);exec(compile(text,str(Path(__file__)),'exec'),ns);result=ns['audit'](directory,methods,data,expected_hash,offline)
 scores=core.read(directory/'scores.json');policy=runner.guard.policy
 infos={(r['group'],r['scenario'],r['trace'],r['decision_period']):r for r in core.read(directory/'information_audits.json')}
 event_map={(r['group'],r['scenario'],r['trace'],r['decision_period']):r for r in scores}
 rules=runner.module('sundial_execution_rules',runner.ROOT/'experiments/deepseek_pilot/rules.py')
 with (directory/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
 row_map={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in rows}
 for group in methods:
  for scenario in ('base','shock'):
   for trace in range(4):
    candidates={}
    for p in range(1,201):
     identity=group,scenario,trace,p;r=event_map.get(identity)
     if r and r.get('generation_event'):candidates={c['id']:rules.compile_rule(c['rule']) for c in r['candidates'] if c['id']!='zero'}
     for node in range(3):
      row=row_map[identity+(node,)];chosen=row['chosen'];assert infos[identity]['chosen']==chosen
      expected=int(row['policy_order'])
      if chosen!='zero':expected=rules.bounded_order(expected,rules.rule_delta(candidates[chosen],infos[identity]['rule_features'][node]))
      assert expected==int(row['actual_order'])
 for r in scores:
  if r.get('execution_failure'):continue
  if r.get('generation_event') and r.get('revision_guard_audit'):
   a=r['revision_guard_audit'];assert a['adopted']==policy.keep_revision(a['original_score'],a['revised_score'],r['search_revision_feedback'][0])
  ranked=sorted((i for i in range(1,4) if policy.eligible(r['search'][i],r['search'][0])),key=lambda i:(r['search'][i]['cost'],i))
  expected='zero';actual=r['review_candidates'];assert len(actual)<=len(ranked)
  for i,item in zip(ranked,actual):
   assert item['id']==r['search'][i]['id'] and item['passed']==policy.eligible(item['score'],r['validation_zero'])
   if item['passed']:assert item is actual[-1];expected=item['id']
  if expected=='zero':assert len(actual)==len(ranked)
  assert r['chosen']==expected and r['candidate_score_calls']<=8
  a=r['forecast_audit'];p=r['decision_period'];trace=r['trace'];age=(p-1)%3
  assert a['group']==r['group'] and a['decision_period']==p and a['report_age']==age
  blocks=[sum(data['shock'][trace][j:j+3])/3 for j in range(0,p-1-age,3)];history=[v for x in blocks for v in [x]*3]
  if r['group']=='original_merton':pair=runner.original.forecasts(history,trace,p-1,'merton',age)
  elif r['group']=='center_naive':
   assert a['center']==[blocks[-1]]*a['horizon'];value=runner.paths.generate(a['center'],blocks[-1],age,a['stream_identity']);assert value['stream_seeds']==a['stream_seeds'];pair=value['deployment'][:3],value['deployment'][3:]
  else:
   v=a['prediction'];assert v['block_history']==blocks and v['revision']==runner.predictor.REVISION
   assert v['adapted']==(r['group']=='adapted_sundial') and v['adapter_sha256']==core.digest(runner.predictor.ADAPTER)
   raw=np.asarray(v['raw_blocks']);assert raw.shape==(32,math.ceil((age+a['horizon'])/3)) and np.isfinite(raw).all()
   assert v['sampling_seeds']==[runner.predictor.stream_seed(a['stream_identity'],purpose) for purpose in ('search','review')]
   bounded=np.clip(raw,0,20);weights=core.read(runner.predictor.ADAPTER)['weights']
   selected=runner.predictor.correction.transform(bounded,runner.predictor.correction.features(blocks,bounded,age),weights) if v['adapted'] else bounded
   assert np.array_equal(selected,np.asarray(v['selected_blocks']))
   reconstructed=independent_allocate(selected,age,a['horizon'],a['stream_identity'],runner.predictor.stream_seed)
   assert reconstructed==v['diagnostic_paths'];assert np.floor(3*selected+.5).astype(int).tolist()==v['allocation_totals']
   pair=([reconstructed[i] for i in (0,1,2)],[reconstructed[i] for i in (16,17,18)])
  assert json.dumps(pair)==json.dumps(r['forecasts'])
 # Common normal/pre-notice environment and actors; no historical reference at new backgrounds.
 for row in rows:
  s,t,p,n=row['scenario'],int(row['trace']),int(row['period']),int(row['node'])
  if s=='base' or p<data['events'][t]['start_index']+3:
   reference=row_map['original_merton',s,t,p,n]
   assert all(row[k]==reference[k] for k in ('cost','inventory','backlog','policy_order','actual_order'))
 model=core.read(directory/'forecast_model_checks.json');assert model['before']==model['after'] and model['unchanged'] and model['adapter_sha256']==core.digest(runner.predictor.ADAPTER)
 result.update(guard_pool_recomputed=True,period_allocations_independently_recomputed=True,executed_dsl_recomputed=True,matched_normal_pre_notice=True,
   sundial_model_unchanged=True,source_sha256=core.source_hashes(),system_sha256=hashlib.sha256(core.SYSTEM.encode()).hexdigest())
 core.write(directory/'audit.json',result);return result
