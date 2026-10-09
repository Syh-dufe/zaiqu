"""Exercise controller generation and rescreen with deterministic, no-network stubs."""
from pathlib import Path
import sys
import types
import importlib.util

root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'experiments/deepseek_refinement'))
sys.path.insert(0,str(root/'experiments/online_llm'))
import controller as original
sys.path.insert(0,str(Path(__file__).parent))
spec=importlib.util.spec_from_file_location('isolated_guard_pool',Path(__file__).with_name('controller.py'))
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
identity=dict(group='guard_pool',scenario='shock',trace=0)
class Reports:
    delivered_history=[];deliveries=[];age=0
    def public_state(self):return dict(delivered_through_period=1)
    def projection(self):return {}
class Client:
    def reset_episode(self):pass
    def generate(self,context,count,identity,stage):
        return [dict(id=('revision' if stage=='revision' else f'initial{i}'),rule={'rules':[]}) for i in range(count)]
env=types.SimpleNamespace(step_num=0,order=[[],[],[]],inventory=[0]*3,backlog=[0]*3)
def score(candidate,*args):
    return dict(id=candidate['id'],cost={'zero':100,'initial0':90,'initial1':92,'initial2':94,'revision':110}[candidate['id']],downstream=5,valid=True)
stub=types.SimpleNamespace(**original.__dict__)
stub.score=score
stub.features=lambda *args:[]
stub.snapshot=lambda *args:{}
stub.forecasts=lambda *args:[[],[]]
stub.corrected=lambda candidate,env,visible,orders,proposed:proposed.copy()
stub.select=lambda *args:('zero',dict(chosen='zero',search=[]))
klass=adapter.build_controller(stub)
for method in ['revision_guard','pool_review','guard_pool']:
    c=klass(method,Client(),[],None,identity)
    action,record=c.decide(env,[],[],[1,2,3],None,None,Reports(),True)
    assert c.events==1 and len(c.candidates)==4 and action==[1,2,3]
    if method in ['revision_guard','guard_pool']:
        assert record['revision_guard_audit']['adopted'] is False
        assert c.candidates[1]['id']=='initial0'
    if method in ['pool_review','guard_pool']:
        assert record['chosen'] in ['initial0','initial1']
        assert record['review_candidates']
    env.step_num=5
    action,record=c.decide(env,[],[],[1,2,3],None,None,Reports(),False)
    assert record['generation_event'] is False and c.events==1
    env.step_num=0
    fresh=klass(method,Client(),[],None,identity)
    assert fresh.events==0 and fresh.memory==[] and fresh.chosen=='zero'
print('CONTROLLER_EVENT_RESCORE_CHECK_PASSED; paid_calls=0; not_real_environment_performance')
