"""Only delivered reports and prior forecasts enter this episode-local state."""
import numpy as np

class MaturedCalibration:
 def __init__(self):
  self.pending={};self.registered=set();self.errors=[];self.previous=[]
 def correct(self,block_history,samples,age,decision_period):
  blocks=list(map(float,block_history));samples=np.asarray(samples,dtype=float)
  assert len(blocks)*3+age==decision_period-1 and blocks[:len(self.previous)]==self.previous
  assert age in (0,1,2) and samples.shape[0]==32 and np.isfinite(samples).all()
  self.previous=blocks
  matured=[]
  for target in sorted(list(self.pending)):
   if target>=len(blocks):continue
   forecast=self.pending.pop(target);entry=dict(block_index=target,predicted=forecast['predicted'],observed=blocks[target],
    error=blocks[target]-forecast['predicted'],forecast_decision=forecast['decision'],available_from_decision=3*(target+1)+1)
   assert entry['available_from_decision']<=decision_period
   self.errors.append(entry);matured.append(entry)
  recent=[e for e in self.errors if len(blocks)-1-e['block_index']<=6][-3:]
  delta=.5*float(np.clip(np.median([e['error'] for e in recent]),-6,6)) if recent else 0.
  adjusted=np.clip(samples+delta,0,20)
  j=1 if age else 0;target=len(blocks)+j;registered=None
  if j<samples.shape[1] and target not in self.registered:
   # Record the OLD adapter's mean so calibration does not recursively feed its own errors.
   registered=dict(block_index=target,predicted=float(samples[:,j].mean()),decision=decision_period)
   self.pending[target]=registered;self.registered.add(target)
  return adjusted,dict(delta=delta,matured=matured,recent=recent,registered=registered,
   report_count=len(blocks),decision_period=decision_period,report_age=age,pending_count=len(self.pending),
   max_shift=3,forecast_error_target='old_adapter_first_fully_future_block')
