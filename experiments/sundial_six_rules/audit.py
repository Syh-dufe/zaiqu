"""Full original audits with bound cached comparator normal/pre-notice rows."""
import csv,inspect
from pathlib import Path
def audit(runner,directory,data,expected_hash,offline=False):
 core=runner.core
 protocol=core.read(Path(directory)/'protocol.json');seed=protocol['training_seed']
 ref=runner.ROOT/f'results/online_llm_guard_pool/development_v1/runs/development_batch01_seed{seed}'
 assert core.read(ref/'demands.json')==data
 check=core.read(ref/'completed.json')['parameter_checks']['guard_pool']
 assert check['before']==check['after']==expected_hash
 with (ref/'periods.csv').open(encoding='utf-8',newline='') as f:
  reference_rows={('original_merton',r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):dict(r,group='original_merton') for r in csv.DictReader(f) if r['group']=='guard_pool'}
 for record in core.read(Path(directory)/'scores.json'):
  if record.get('generation_event'):
   for candidate in record['candidates']:
    if candidate['id']!='zero':assert 1<=len(candidate['rule']['rules'])<=6
 old=runner.module('cached_original_sundial_auditor',runner.ROOT/'experiments/sundial_closed_loop_development/audit.py');text=inspect.getsource(old.audit)
 marker=" row_map={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in rows}";assert text.count(marker)==1;text=text.replace(marker,marker+'\n row_map.update(REFERENCE_ROWS)')
 marker="raw=np.asarray(v['raw_blocks'])";assert text.count(marker)==1;text=text.replace(marker,"raw=np.asarray(v['raw_blocks'],dtype=np.float64)")
 marker="   assert np.array_equal(selected,np.asarray(v['selected_blocks']))";assert text.count(marker)==1
 replacement="""   assert np.array_equal(selected,np.asarray(v['base_selected_blocks']))
   delivered=np.asarray(blocks,dtype=float);previous=delivered[max(0,len(delivered)-11):-1]
   z=float((delivered[-1]-np.mean(delivered[-4:-1]))/max(1.,float(np.std(previous)))) if len(delivered)>=4 else 0.
   state='up' if z>.5 else 'down' if z<-.5 else 'flat';coefficient=.5*3/(3+age)
   shift=np.clip(coefficient*(float(delivered[-1])-selected.mean(0)),-4,4)
   selected=np.clip(selected+shift[None,:],0,20)
   response=v['response'];assert response['candidate']=='all_half' and response['state']==state and response['z']==z and response['coefficient']==coefficient
   assert np.array_equal(shift,np.asarray(response['block_shifts']))
   assert np.array_equal(selected,np.asarray(v['selected_blocks']))"""
 text=text.replace(marker,replacement);ns=dict(old.__dict__,REFERENCE_ROWS=reference_rows);exec(compile(text,str(Path(__file__)),'exec'),ns);result=ns['audit'](runner,directory,data,expected_hash,offline)
 calls=runner.core.read(Path(directory)/'calls.json');assert len(calls)<=64 and sum(c['attempt']==1 for c in calls)<=32
 for trace in range(4):
  events=[s for s in runner.core.read(Path(directory)/'scores.json') if s['trace']==trace and s.get('generation_event')];assert len(events)==4
  if not offline:
   valid={(c['event'],c['stage']) for c in calls if c['trace']==trace and c['status']=='valid'};assert valid=={(e,s) for e in range(1,5) for s in ('initial','revision')}
 result.update(rule_limit=6,historical_merton_rule_limit=4,historical_guard_pool_merton_reused=True,historical_directory=str(ref),response_recomputed=True,actual_variant='response_all_half_real_guard_pool',api_http=len(calls),semantic=sum(c['attempt']==1 for c in calls));runner.core.write(Path(directory)/'audit.json',result);return result
