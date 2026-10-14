"""Paired stratified bootstrap at independent demand-path level."""
import numpy as np
from common import OUT,read,write
def crps(x,y):return float((np.abs(x-y).mean(axis=0)-.5*np.abs(x[:,None,:]-x[None,:,:]).mean(axis=(0,1))).mean())
def analyze():
 cases=read(OUT/'cases.json');pred={r['case_id']:r for r in read(OUT/'predictions.json')};assert len(pred)==len(cases)==120
 rows=[];scoring=[]
 for c in cases:
  p=pred[c['id']];y=np.asarray(c['future_label']);starts=[s for s in range(-c['report_age'],20,3) if 0<=s and s+3<=20]
  labels=np.asarray([y[s:s+3].mean() for s in starts])
  for method,values in [('merton',p['merton']['paths']),('sundial',p['sundial_period_paths'])]:
   x=np.asarray(values,dtype=float);assert x.shape==(32,20)
   b=np.stack([x[:,s:s+3].mean(axis=1) for s in starts],axis=1)
   rows.append(dict(case_id=c['id'],path_id=c['path_id'],type=c['type'],method=method,block_crps=crps(b,labels),block_mae=float(np.abs(b.mean(axis=0)-labels).mean()),period_mae=float(np.abs(x.mean(axis=0)-y).mean()),total_crps=crps(x.sum(axis=1)[:,None],np.array([y.sum()]))))
   scoring.append(dict(case_id=c['id'],method=method,block_samples=b.tolist(),block_labels=labels.tolist()))
 paths=[]
 for pid in sorted({c['path_id'] for c in cases}):
  local=[r for r in rows if r['path_id']==pid];assert len(local)==12
  means={m:{k:float(np.mean([r[k] for r in local if r['method']==m])) for k in ('block_crps','block_mae','period_mae','total_crps')} for m in ('merton','sundial')}
  paths.append(dict(path_id=pid,type=local[0]['type'],means=means,difference={k:means['sundial'][k]-means['merton'][k] for k in means['sundial']}))
 types=sorted({p['type'] for p in paths});assert len(types)==4
 diff=np.asarray([[ [p['difference'][k] for k in ('block_crps','block_mae')] for p in paths if p['type']==kind] for kind in types]);assert diff.shape==(4,5,2)
 rng=np.random.default_rng(20271751);idx=rng.integers(0,5,size=(20000,4,5))
 samples=np.stack([diff[t][idx[:,t]].mean(axis=1) for t in range(4)],axis=1).mean(axis=1)
 contrasts={k:dict(mean=float(diff[:,:,i].mean()),ci_97_5=np.quantile(samples[:,i],[.0125,.9875]).tolist()) for i,k in enumerate(('block_crps','block_mae'))}
 by_type={t:{m:{k:float(np.mean([p['means'][m][k] for p in paths if p['type']==t])) for k in ('block_crps','block_mae','period_mae','total_crps')} for m in ('merton','sundial')} for t in types}
 overall={m:{k:float(np.mean([p['means'][m][k] for p in paths])) for k in ('block_crps','block_mae','period_mae','total_crps')} for m in ('merton','sundial')}
 supported=all(v['mean']<0 and v['ci_97_5'][1]<0 for v in contrasts.values()) and not any(v['sundial']['block_crps']>v['merton']['block_crps'] and v['sundial']['block_mae']>v['merton']['block_mae'] for v in by_type.values())
 write(OUT/'metrics.json',dict(overall=overall,contrasts=contrasts,by_type=by_type,paths=paths,per_case=rows,strong_prediction_support=bool(supported),bootstrap_seed=20271751,replicates=20000))
 write(OUT/'scoring_values.json',scoring)
 print('EXPANDED_STATISTICS_COMPLETE',overall,contrasts,bool(supported),flush=True)
if __name__=='__main__':analyze()
