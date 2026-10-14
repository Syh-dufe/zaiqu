import numpy as np
from common import OUT,read,write,digest,verify_freeze
from adapter import features,transform
def crps(x,y):return float((np.abs(x-y).mean(axis=0)-.5*np.abs(x[:,None,:]-x[None,:,:]).mean(axis=(0,1))).mean())
def evaluate():
 verify_freeze();fit=read(OUT/'fit_completed.json');reg=read(OUT/'test_registration.json')
 assert digest(OUT/'best_adapter.json')==fit['best_sha256']==reg['adapter_sha256']
 cases=read(OUT/'test_cases.json');pred={r['case_id']:r for r in read(OUT/'test_predictions.json')};weights=read(OUT/'best_adapter.json')['weights'];rows=[];raw=[]
 for c in cases:
  p=pred[c['id']];s=np.asarray(p['blocks'],dtype=float);f=features(c['block_history'],s,c['report_age']);a=transform(s,f,weights)
  y=np.asarray(c['future_label']);starts=[t for t in range(-c['report_age'],20,3) if 0<=t and t+3<=20];labels=np.asarray([y[t:t+3].mean() for t in starts]);indices=[(t+c['report_age'])//3 for t in starts]
  methods={'sundial':s[:,indices],'adapted':a[:,indices]}
  for name in ('merton','naive'):
   v=np.asarray(p[name]['paths']);methods[name]=np.stack([v[:,t:t+3].mean(axis=1) for t in starts],axis=1)
  for m,x in methods.items():
   rows.append(dict(case_id=c['id'],path_id=c['path_id'],type=c['type'],method=m,crps=crps(x,labels),mae=float(np.abs(x.mean(axis=0)-labels).mean())))
   raw.append(dict(case_id=c['id'],method=m,block_samples=x.tolist(),labels=labels.tolist()))
 path_rows=[]
 for pid in sorted({c['path_id'] for c in cases}):
  local=[r for r in rows if r['path_id']==pid];assert len(local)==24
  means={m:{k:float(np.mean([r[k] for r in local if r['method']==m])) for k in ('crps','mae')} for m in methods}
  path_rows.append(dict(path_id=pid,type=local[0]['type'],means=means))
 overall={m:{k:float(np.mean([p['means'][m][k] for p in path_rows])) for k in ('crps','mae')} for m in methods};types=sorted({p['type'] for p in path_rows})
 diff=np.asarray([[[p['means']['adapted']['crps']-p['means'][m]['crps'] for m in ('sundial','merton')] for p in path_rows if p['type']==t] for t in types]);assert diff.shape==(4,5,2)
 rng=np.random.default_rng(20271951);idx=rng.integers(0,5,size=(20000,4,5));samples=np.stack([diff[t][idx[:,t]].mean(axis=1) for t in range(4)],axis=1).mean(axis=1)
 contrasts={m:dict(mean=float(diff[:,:,i].mean()),ci_97_5=np.quantile(samples[:,i],[.0125,.9875]).tolist()) for i,m in enumerate(('sundial','merton'))}
 supported=all(v['mean']<0 and v['ci_97_5'][1]<0 for v in contrasts.values()) and all(overall['adapted']['mae']<=overall[m]['mae'] for m in ('sundial','merton'))
 write(OUT/'metrics.json',dict(overall=overall,contrasts=contrasts,paths=path_rows,per_case=rows,gate_passed=bool(supported),bootstrap_seed=20271951,replicates=20000));write(OUT/'scoring_values.json',raw)
 print('ADAPTER_VALIDATION_METRICS',overall,contrasts,bool(supported),flush=True)
if __name__=='__main__':evaluate()
