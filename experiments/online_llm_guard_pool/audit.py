"""Raw deployment audit plus independently reconstructed upgrade decisions."""
import inspect
from pathlib import Path
from runner import ROOT,module,policy,METHODS

legacy=module('guard_pool_raw_audit',ROOT/'experiments/submission_required/audit.py')
source=inspect.getsource(legacy.audit)
before="('online_feedback','no_feedback','no_review','first_only')"
assert source.count(before)==1
source=source.replace(before,"('online_feedback','revision_guard','pool_review','guard_pool')")
namespace=dict(legacy.__dict__)
exec(compile(source,str(Path(__file__)),'exec'),namespace)
raw_audit=namespace['audit']

def audit(directory,data,expected_hash,offline=False):
    directory=Path(directory)
    result=raw_audit(directory,METHODS,data,expected_hash,offline)
    scores=legacy.read(directory/'scores.json')
    guarded=reviews=0
    for record in scores:
        if record.get('execution_failure'):continue
        method=record['group']
        assert method in METHODS
        if method in ('revision_guard','guard_pool') and record.get('generation_event'):
            decision=record.get('revision_guard_audit')
            if decision:
                assert decision['adopted']==policy.keep_revision(decision['original_score'],decision['revised_score'],record['search_revision_feedback'][0])
                assert decision['extra_score_calls']==1
                guarded+=1
        if method in ('pool_review','guard_pool'):
            search=record['search'];assert len(search)==4
            ranked=sorted((i for i in range(1,4) if policy.eligible(search[i],search[0])),key=lambda i:(search[i]['cost'],i))
            actual=record['review_candidates']
            assert len(actual)<=3 and len(actual)<=len(ranked)
            assert record['candidate_score_calls']==4+int(record['validation_zero'] is not None)+len(actual)
            assert record['candidate_score_calls']<=8
            expected='zero'
            for index,item in zip(ranked,actual):
                assert item['id']==search[index]['id']
                assert item['passed']==policy.eligible(item['score'],record['validation_zero'])
                if item['passed']:
                    assert item is actual[-1];expected=item['id']
            if expected=='zero':assert len(actual)==len(ranked)
            assert record['chosen']==expected
            if not ranked:assert record['validation_zero'] is None and not actual
            reviews+=len(actual)
    result.update(revision_decisions_recomputed=guarded,pool_candidate_reviews_recomputed=reviews,
        upgrade_decisions_checked=True,status='passed')
    legacy.write(directory/'audit.json',result)
    return result
