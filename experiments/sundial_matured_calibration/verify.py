"""Independent causal-state and scalar scoring recomputation, no calibrator import."""
import hashlib,json,math,statistics
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_matured_calibration/v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
done=read(OUT/'completed.json');assert done['api']==0 and done['new_paths']==12 and done['new_windows']==180
for p,sha in read(OUT/'freeze.json')['sha256'].items():assert digest(Path(p))==sha,p
max_error=0;counts={}
for phase in ('cached','validation'):
 audits=read(OUT/f'{phase}_audits.json');windows={r['window_id']:r for r in read(OUT/f'{phase}_windows.json')};metrics=read(OUT/f'{phase}_metrics.json');pending={};seen={};errors={};previous={}
 for r in audits:
  pid=r['path_id'];w=windows[r['window_id']];h=r['block_history'];p=w['decision_period'];assert len(h)*3+r['age']==p-1 and h[:len(previous.get(pid,[]))]==previous.get(pid,[]);previous[pid]=h
  pending.setdefault(pid,{});seen.setdefault(pid,set());errors.setdefault(pid,[]);matured=[]
  for index in sorted(list(pending[pid])):
   if index>=len(h):continue
   forecast,origin=pending[pid].pop(index);entry=dict(block_index=index,predicted=forecast,observed=h[index],error=h[index]-forecast,
    forecast_decision=origin,available_from_decision=3*(index+1)+1);assert entry['available_from_decision']<=p;errors[pid].append(entry);matured.append(entry)
  recent=[e for e in errors[pid] if len(h)-1-e['block_index']<=6][-3:]
  delta=.5*max(-6,min(6,statistics.median(e['error'] for e in recent))) if recent else 0.
  assert abs(delta-r['calibration']['delta'])<1e-12 and len(matured)==len(r['calibration']['matured'])
  for x,y in zip(matured,r['calibration']['matured']):
   for k in ('predicted','observed','error'):assert abs(x[k]-y[k])<1e-12
   for k in ('block_index','forecast_decision','available_from_decision'):assert x[k]==y[k]
  base=np.asarray(r['base_blocks']);assert np.allclose(np.clip(base+delta,0,20),r['adjusted_blocks'],rtol=0,atol=1e-12)
  j=1 if r['age'] else 0;index=len(h)+j
  if j<base.shape[1] and index not in seen[pid]:
   # First fully future block starts at 3*index+1, at/after this decision.
   assert 3*index+1>=p;forecast=sum(base[:,j])/32;pending[pid][index]=(forecast,p);seen[pid].add(index)
  assert len({e['block_index'] for e in errors[pid]})==len(errors[pid])
 lookup={(r['window_id'],r['method']):r for r in metrics['per_window']}
 for r in read(OUT/f'{phase}_scoring.json'):
  x=np.asarray(r['samples']);y=np.asarray(r['labels']);n=len(x);scores=[]
  for col,truth in enumerate(y):
   s=sorted(x[:,col]);scores.append(sum(abs(v-truth) for v in s)/n-sum((2*k-n-1)*v for k,v in enumerate(s,1))/n**2)
  score=sum(scores)/len(scores);mae=sum(abs(sum(x[:,j])/n-v) for j,v in enumerate(y))/len(y);bias=sum(sum(x[:,j])/n-v for j,v in enumerate(y))/len(y);stored=lookup[r['window_id'],r['method']]
  for k,v in [('crps',score),('mae',mae),('bias',bias)]:max_error=max(max_error,abs(v-stored[k]));assert abs(v-stored[k])<1e-10
 for path in metrics['paths']:
  for method,values in path['means'].items():
   local=[r for r in metrics['per_window'] if r['path_id']==path['path_id'] and r['method']==method]
   for k in ('crps','mae','bias'):assert abs(np.mean([r[k] for r in local])-values[k])<1e-12
 counts[phase]=dict(windows=len(windows),paths=len(metrics['paths']),unique_matured_errors=sum(len(v) for v in errors.values()))
hist=set(read(OUT/'historical.json')['consumed_hashes']);seen=set();inputs={r['path_id']:r for r in read(OUT/'validation_inputs.json')}
for item in inputs.values():
 base=item['base'][0];shock=base.copy()
 for interval in item['event']['intervals']:
  for j in range(interval['start'],interval['end']):shock[j]=min(20,math.ceil(base[j]*interval['factor'])) if interval['factor']>1 else math.floor(base[j]*interval['factor'])
 assert shock==item['shock'][0]
 pair={hashlib.sha256(json.dumps(v,separators=(',',':')).encode()).hexdigest() for v in (base,shock)};assert not pair&hist and not pair&seen;seen.update(pair)
for w in read(OUT/'validation_windows.json'):
 v=inputs[w['path_id']]['shock'][0];n=w['decision_period']-1;assert np.allclose(w['block_history'],[sum(v[j:j+3])/3 for j in range(0,n-n%3,3)],rtol=0,atol=1e-12);assert w['future_label']==v[n:n+20]
model=read(OUT/'model_checks.json');assert model['before']==model['after'] and model['unchanged']
record=dict(status='passed',causal_matured_labels=True,first_fully_future_block=True,unique_report_labels=True,episode_reset=True,independent_scalar_metrics=True,max_metric_error=max_error,
 new_inputs_collision_free=True,new_reports_reconstructed=True,source_model_adapter_hashes=True,api=0,counts=counts)
(OUT/'independent_verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print('MATURED_CALIBRATION_INDEPENDENT_AUDIT',record)
