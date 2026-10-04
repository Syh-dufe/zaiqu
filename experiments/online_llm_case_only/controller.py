"""Original event behavior for every LLM method; labels are audit metadata."""
import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
ALIAS='case_only_original_controller'
if ALIAS in sys.modules:
    ORIGINAL=sys.modules[ALIAS]
    if Path(ORIGINAL.__file__).resolve()!=ROOT/'experiments/online_llm/controller.py':
        raise RuntimeError('Original controller alias collision')
else:
    spec=importlib.util.spec_from_file_location(ALIAS,ROOT/'experiments/online_llm/controller.py')
    ORIGINAL=importlib.util.module_from_spec(spec);sys.modules[ALIAS]=ORIGINAL;spec.loader.exec_module(ORIGINAL)
V1Controller=ORIGINAL.EventController

class FeedbackController(V1Controller):
    def __init__(self,group,client,identity):
        if group not in ('online_feedback','case_feedback'):
            raise ValueError('Unregistered feedback method')
        self.audit_method=group
        # Keep original feedback triggers, revision index0, expiry and memory.
        super().__init__('online_feedback',client,[],None,identity)

    def decide(self,*args,**kwargs):
        actual,record=super().decide(*args,**kwargs)
        if record:
            record['method']=self.audit_method
        return actual,record
