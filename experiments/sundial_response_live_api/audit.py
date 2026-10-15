"""Retain complete original API/DSL/guard audits with independent response math."""
import inspect
import numpy as np
def audit(runner,directory,data,expected_hash,offline=False):
 old=runner.module('response_live_original_auditor',runner.ROOT/'experiments/sundial_closed_loop_development/audit.py')
 text=inspect.getsource(old.audit)
 needle="raw=np.asarray(v['raw_blocks'])";assert text.count(needle)==1;text=text.replace(needle,"raw=np.asarray(v['raw_blocks'],dtype=np.float64)")
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
 text=text.replace(needle,replacement);ns=dict(old.__dict__);exec(compile(text,str(__file__),'exec'),ns)
 result=ns['audit'](runner,directory,data,expected_hash,offline)
 calls=runner.core.read(directory/'calls.json');assert len(calls)<=128 and sum(c['attempt']==1 for c in calls)<=64
 for group in runner.METHODS:
  for trace in range(4):
   records=[s for s in runner.core.read(directory/'scores.json') if s['group']==group and s['trace']==trace and s.get('generation_event')];assert len(records)==4
   if not offline:
    local=[c for c in calls if c['group']==group and c['trace']==trace];assert len(local)<=16
    valid={(c['event'],c['stage']) for c in local if c['status']=='valid'};assert valid=={(e,stage) for e in range(1,5) for stage in ('initial','revision')}
 result.update(actual_variant='response_all_half_real_guard_pool',response_recomputed=True,api_http=len(calls),semantic=sum(c['attempt']==1 for c in calls))
 runner.core.write(directory/'audit.json',result);return result
