"""Frozen Sundial with the frozen multiscale24 adapter, no path compression."""
import importlib.util,json,sys,time,math,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('cost_frozen_sundial_predictor',ROOT/'experiments/sundial_closed_loop_development/predictor.py');base=importlib.util.module_from_spec(s);sys.modules[s.name]=base;s.loader.exec_module(base)
REVISION=base.REVISION;ADAPTER=ROOT/'results/sundial_multiscale_adapter/v1/multiscale24_best.json'
parameter_hash=base.parameter_hash;stream_seed=base.stream_seed;correction=base.correction;allocate=base.allocate
class Centers:
 def __init__(self):self.cache={}
 def forecast(self,history,age,horizon,identity,adapted):
  assert adapted and len(history)%3==0 and age in (0,1,2)
  blocks=[]
  for i in range(0,len(history),3):assert history[i]==history[i+1]==history[i+2];blocks.append(float(history[i]))
  count=math.ceil((age+horizon)/3);key=(tuple(blocks),count,identity);hit=key in self.cache;start=time.perf_counter()
  if not hit:self.cache[key]=base.sample_blocks(blocks,count,identity)
  raw,seeds=self.cache[key];bounded=np.clip(raw.astype(np.float64),0,20);weights=json.loads(ADAPTER.read_text(encoding='utf-8'))['weights']
  selected=correction.transform(bounded,correction.features(blocks,bounded,age),weights);value=allocate(selected,age,horizon,identity)
  return value,dict(block_history=blocks,raw_blocks=raw.tolist(),selected_blocks=selected.tolist(),sampling_seeds=seeds,cache_hit=hit,seconds=time.perf_counter()-start,revision=REVISION,adapter_sha256=hashlib.sha256(ADAPTER.read_bytes()).hexdigest(),adapted=True,allocation_totals=value['totals'],allocation_seeds=value['allocation_seeds'],diagnostic_paths=value['paths'],actual_variant='multiscale24',calibration_dtype='float64')
