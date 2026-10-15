"""Frozen multiscale samples, response location shift, original random allocation."""
import importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
base=module('response_frozen_multiscale',ROOT/'experiments/sundial_multiscale_cost/predictor.py');response=module('causal_response_math',HERE/'response.py')
ADAPTER=base.ADAPTER;REVISION=base.REVISION;parameter_hash=base.parameter_hash;CANDIDATE='zero'
class Centers:
 def __init__(self):self.original=base.Centers()
 def forecast(self,history,age,horizon,identity,adapted):
  old,audit=self.original.forecast(history,age,horizon,identity,adapted)
  samples,metadata=response.apply(audit['selected_blocks'],audit['block_history'],age,CANDIDATE)
  value=base.allocate(samples,age,horizon,identity)
  audit.update(base_selected_blocks=audit['selected_blocks'],selected_blocks=samples.tolist(),base_random_paths=old['paths'],response=metadata,allocation_totals=value['totals'],allocation_seeds=value['allocation_seeds'],diagnostic_paths=value['paths'],actual_variant='change_response_'+CANDIDATE)
  return value,audit
