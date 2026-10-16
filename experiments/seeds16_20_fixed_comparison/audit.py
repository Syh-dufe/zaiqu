"""Frozen raw/forecast audits with explicit three-trace and new-reference binding."""
import csv,inspect
from pathlib import Path
def audit(runner,directory,data,expected_hash,reference=None,offline=False):
 core=runner.core;directory=Path(directory);methods=runner.METHODS
 legacy=runner.module('extension_base_raw_audit',runner.ROOT/'experiments/submission_required/audit.py')
 text=inspect.getsource(legacy.audit)
 text=text.replace('range(4)','range(3)').replace('len(methods)*8','len(methods)*6').replace('len(methods)*1600','len(methods)*1200')
 needle="('online_feedback','no_feedback','no_review','first_only')";assert text.count(needle)==1;text=text.replace(needle,repr(methods))
 needle="context=__import__('json').loads(content)";assert text.count(needle)==1;text=text.replace(needle,needle+";context=context.get('context',context)")
 ns=dict(legacy.__dict__,read=core.read,write=core.write,digest=core.digest);exec(compile(text,str(Path(__file__)),'exec'),ns);raw_audit=ns['audit']
 old=runner.module('extension_frozen_forecast_audit',runner.ROOT/'experiments/sundial_closed_loop_development/audit.py')
 text=inspect.getsource(old.audit);start=text.index(" legacy=runner.module(");end=text.index(" scores=core.read(",start)
 text=text[:start]+" result=RAW_AUDIT(directory,methods,data,expected_hash,offline)\n"+text[end:]
 text=text.replace('range(4)','range(3)')
 refs={}
 if reference is not None:
  assert core.read(reference/'demands.json')==data
  checks=core.read(reference/'completed.json')['parameter_checks'];assert all(x['before']==x['after']==expected_hash for x in checks.values())
  with (reference/'periods.csv').open(encoding='utf-8',newline='') as f:
   refs={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in csv.DictReader(f) if r['group']=='original_merton'}
  assert len(refs)==3600
 needle=" row_map={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in rows}";assert text.count(needle)==1;text=text.replace(needle,needle+'\n row_map.update(REFERENCE_ROWS)')
 # Pure HAPPO produces no forecast score records. Its execution is zero-correction.
 needle=" if r['group']=='original_merton':pair=";assert needle in text
 text=text.replace("raw=np.asarray(v['raw_blocks'])","raw=np.asarray(v['raw_blocks'],dtype=np.float64)")
 needle="   assert np.array_equal(selected,np.asarray(v['selected_blocks']))";assert text.count(needle)==1
 replacement="""   assert np.array_equal(selected,np.asarray(v['base_selected_blocks']))
   delivered=np.asarray(blocks,dtype=float);previous=delivered[max(0,len(delivered)-11):-1]
   z=float((delivered[-1]-np.mean(delivered[-4:-1]))/max(1.,float(np.std(previous)))) if len(delivered)>=4 else 0.
   state='up' if z>.5 else 'down' if z<-.5 else 'flat';coefficient=.5*3/(3+age)
   shift=np.clip(coefficient*(float(delivered[-1])-selected.mean(0)),-4,4)
   selected=np.clip(selected+shift[None,:],0,20)
   response=v['response'];assert response['candidate']=='all_half' and response['state']==state and response['z']==z and response['coefficient']==coefficient
   assert np.array_equal(shift,np.asarray(response['block_shifts']))
   assert np.array_equal(selected,np.asarray(v['selected_blocks']))"""
 text=text.replace(needle,replacement)
 ns=dict(old.__dict__,RAW_AUDIT=raw_audit,REFERENCE_ROWS=refs);exec(compile(text,str(Path(__file__)),'exec'),ns)
 result=ns['audit'](runner,directory,data,expected_hash,offline)
 calls=core.read(directory/'calls.json');assert len(calls)<=48 and sum(c['attempt']==1 for c in calls)<=24
 scores=core.read(directory/'scores.json')
 for trace in range(3):
  active='original_merton' if 'original_merton' in methods else 'adapted_sundial'
  events=[s for s in scores if s['group']==active and s['trace']==trace and s.get('generation_event')];assert len(events)==4
  for event in events:
   for candidate in event['candidates']:
    if candidate['id']!='zero':assert 1<=len(candidate['rule']['rules'])<=(4 if active=='original_merton' else 6)
  if not offline:
   valid={(c['event'],c['stage']) for c in calls if c['trace']==trace and c['status']=='valid'};assert valid=={(e,s) for e in range(1,5) for s in ('initial','revision')}
 result.update(rule_limit=4 if 'original_merton' in methods else 6,traces=3,api_http=len(calls),semantic=sum(c['attempt']==1 for c in calls),response_recomputed=True,model_seed=core.read(directory/'protocol.json')['training_seed'])
 core.write(directory/'audit.json',result);return result
