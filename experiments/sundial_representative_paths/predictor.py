"""Replacement deployment wrapper; frozen predictor and samples unchanged."""
import importlib.util,sys
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
base=load('representative_frozen_sundial_predictor',ROOT/'experiments/sundial_closed_loop_development/predictor.py')
selection=load('representative_selection',HERE/'selection.py')
REVISION=base.REVISION;ADAPTER=base.ADAPTER
model=base.model;parameter_hash=base.parameter_hash
class Centers(base.Centers):
 def forecast(self,*args,**kwargs):
  values,audit=super().forecast(*args,**kwargs)
  deployed,check=selection.select(values['paths'])
  return dict(values,deployment=deployed),dict(audit,path_selection=check,previous_indices=[0,1,2,16,17,18])
