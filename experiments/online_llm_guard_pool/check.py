"""No-API boundary checks for the mechanism; not closed-loop performance evidence."""
from policy import keep_revision, select_pool

def value(name, cost, service=5, valid=True):
    return dict(id=name, cost=cost, downstream=service, valid=valid)

zero=value('zero',100,10)
old=value('a',95)
assert keep_revision(old,value('new',94),zero)
for revised in [value('new',95),value('new',96),value('new',94,6),
                value('new',float('nan')),value('new',90,valid=False)]:
    assert not keep_revision(old,revised,zero)
assert not keep_revision(value('a',99,10),value('new',98,11),zero)
assert keep_revision(value('a',0,valid=False),value('new',95),zero)
assert not keep_revision(value('a',0,valid=False),value('new',100),zero)
candidates=[dict(id=n) for n in ['zero','a','b','c']]
search=[zero,value('a',90),value('b',92),value('c',94)]
review=[zero,value('a',110),value('b',98),value('c',95)]
calls=[]
def score(candidate, phase):
    i=[c['id'] for c in candidates].index(candidate['id']);calls.append((phase,i))
    return (search if phase==0 else review)[i]
chosen, audit=select_pool(candidates,score)
assert chosen=='b' and len(audit['review_candidates'])==2 and len(calls)==7
assert (1,3) not in calls and audit['candidate_score_calls']==7
review=[zero,value('a',100),value('b',100),value('c',100)]
chosen,audit=select_pool(candidates,score)
assert chosen=='zero' and len(audit['review_candidates'])==3 and audit['candidate_score_calls']==8
chosen,audit=select_pool(candidates,score,review=False)
assert chosen=='a' and audit['validation_zero'] is None and audit['candidate_score_calls']==4
search=[zero,value('a',100),value('b',100),value('c',100)]
chosen,audit=select_pool(candidates,score)
assert chosen=='zero' and audit['candidate_score_calls']==4
print('GUARD_POOL_CHECK_PASSED; paid_calls=0; not_performance_evidence=True')
