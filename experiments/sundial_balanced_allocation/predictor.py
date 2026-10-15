"""Exact same frozen block forecasts; replace only block-to-period allocation."""
import importlib.util,sys,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('balanced_original_predictor',ROOT/'experiments/sundial_multiscale_cost/predictor.py')
base=importlib.util.module_from_spec(s);sys.modules[s.name]=base;s.loader.exec_module(base)
ADAPTER=base.ADAPTER;REVISION=base.REVISION;parameter_hash=base.parameter_hash
def allocate(blocks,age,horizon):
 blocks=np.asarray(blocks,dtype=float);assert blocks.shape==(32,math.ceil((age+horizon)/3))
 paths=[];totals=[]
 for draw,row in enumerate(blocks):
  sequence=[];total_row=[]
  for j,m in enumerate(row):
   k=int(math.floor(3*float(np.clip(m,0,20))+.5));q,r=divmod(k,3);slots=[q,q,q]
   for d in range(r):slots[(j+draw+d)%3]+=1
   assert sum(slots)==k and max(slots)-min(slots)<=1 and all(0<=v<=20 for v in slots)
   sequence.extend(slots);total_row.append(k)
  paths.append(sequence[age:age+horizon]);totals.append(total_row)
 return dict(paths=paths,deployment=[paths[i] for i in (0,1,2,16,17,18)],totals=totals)
class Centers:
 def __init__(self):self.original=base.Centers()
 def forecast(self,history,age,horizon,identity,adapted):
  old,audit=self.original.forecast(history,age,horizon,identity,adapted)
  value=allocate(audit['selected_blocks'],age,horizon);assert value['totals']==old['totals']
  audit.update(original_random_paths=old['paths'],diagnostic_paths=value['paths'],allocation_totals=value['totals'],allocation_variant='balanced_rotating_remainder',actual_variant='multiscale24_balanced',allocation_seeds_used=False)
  return value,audit
