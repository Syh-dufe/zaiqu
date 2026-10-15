"""Full raw and forecast/controller reconstruction for exactly three timing cases."""
import inspect
from pathlib import Path
def audit(runner,directory,data,expected_hash,offline=False):
    legacy=runner.module('timing_raw_legacy_auditor',runner.ROOT/'experiments/submission_required/audit.py')
    text=inspect.getsource(legacy.audit)
    needle="('online_feedback','no_feedback','no_review','first_only')";assert text.count(needle)==1
    text=text.replace(needle,repr(runner.METHODS)).replace('range(4)','range(3)').replace('len(methods)*8','len(methods)*6').replace('len(methods)*1600','len(methods)*1200')
    needle="context=__import__('json').loads(content)";assert text.count(needle)==1
    text=text.replace(needle,needle+";context=context.get('context',context)")
    ns=dict(legacy.__dict__);exec(compile(text,__file__,'exec'),ns);raw_audit=ns['audit']
    full=runner.module('timing_forecast_legacy_auditor',runner.ROOT/'experiments/sundial_closed_loop_development/audit.py')
    text=inspect.getsource(full.audit);start=text.index(" legacy=runner.module(");end=text.index(" scores=core.read",start)
    text=text[:start]+" result=RAW_AUDIT(directory,methods,data,expected_hash,offline)\n"+text[end:]
    text=text.replace('range(4)','range(3)')
    needle="raw=np.asarray(v['raw_blocks'])";assert text.count(needle)==1
    text=text.replace(needle,"raw=np.asarray(v['raw_blocks'],dtype=np.float64)")
    needle="   assert np.array_equal(selected,np.asarray(v['selected_blocks']))";assert text.count(needle)==1
    text=text.replace(needle,"""   assert np.array_equal(selected,np.asarray(v['base_selected_blocks']))
   delivered=np.asarray(blocks,dtype=float);previous=delivered[max(0,len(delivered)-11):-1]
   z=float((delivered[-1]-np.mean(delivered[-4:-1]))/max(1.,float(np.std(previous)))) if len(delivered)>=4 else 0.
   state='up' if z>.5 else 'down' if z<-.5 else 'flat';coefficient=.5*3/(3+age)
   shift=np.clip(coefficient*(float(delivered[-1])-selected.mean(0)),-4,4)
   selected=np.clip(selected+shift[None,:],0,20)
   response=v['response'];assert response['candidate']=='all_half' and response['state']==state and response['z']==z and response['coefficient']==coefficient
   assert np.array_equal(shift,np.asarray(response['block_shifts']))
   assert np.array_equal(selected,np.asarray(v['selected_blocks']))""")
    ns=dict(full.__dict__,RAW_AUDIT=raw_audit);exec(compile(text,__file__,'exec'),ns)
    result=ns['audit'](runner,directory,data,expected_hash,offline)
    calls=runner.core.read(Path(directory)/'calls.json')
    assert len(calls)<=96 and sum(c['attempt']==1 for c in calls)<=48
    scores=runner.core.read(Path(directory)/'scores.json')
    for group in ('original_merton','adapted_sundial'):
        for trace in range(3):
            events=[s for s in scores if s['group']==group and s['trace']==trace and s.get('generation_event')]
            assert len(events)==4
            for event in events:
                for c in event['candidates']:
                    if c['id']!='zero':assert 1<=len(c['rule']['rules'])<=6
            if not offline:
                valid={(c['event'],c['stage']) for c in calls if c['group']==group and c['trace']==trace and c['status']=='valid'}
                assert valid=={(i,stage) for i in range(1,5) for stage in ('initial','revision')}
    result.update(rule_limit_both=6,timing_offsets=list(runner.OFFSETS),api_http=len(calls),semantic=sum(c['attempt']==1 for c in calls))
    runner.core.write(Path(directory)/'audit.json',result);return result
