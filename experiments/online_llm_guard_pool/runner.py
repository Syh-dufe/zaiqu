"""Independent deployment adapter; preserves original controller and client objects."""
import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
METHODS=('happo','online_feedback','revision_guard','pool_review','guard_pool')

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value)
    return value

core=module('guard_pool_deployment_core',ROOT/'experiments/submission_required/run_online.py')
original=sys.modules['controller']
policy=module('guard_pool_policy',HERE/'policy.py')
previous=sys.modules.get('policy')
sys.modules['policy']=policy
try:adapter=module('guard_pool_controller_adapter',HERE/'controller.py')
finally:
    if previous is None:sys.modules.pop('policy',None)
    else:sys.modules['policy']=previous
core.EventController=adapter.factory(original)
core.METHODS=METHODS
old_hashes=core.source_hashes
def source_hashes():
    hashes=old_hashes()
    files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/specs/2026-10-10-online-guard-pool-design.md',
        ROOT/'docs/superpowers/plans/2026-10-10-online-guard-pool.md']
    hashes.update({str(p.relative_to(ROOT)):core.digest(p) for p in files})
    return hashes
core.source_hashes=source_hashes
old_contracts=core.contracts
def contracts(*args,**kwargs):
    value=old_contracts(*args,**kwargs)
    value.update(development_only=True,independent_confirmation=False,
        upgrade='revision_guard_and_pool_review',max_pool_review_candidates=3,
        max_pool_selection_score_calls=8,max_guard_extra_score_calls_per_event=1)
    return value
core.contracts=contracts

if __name__=='__main__':core.main()
