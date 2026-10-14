"""Future labels are owned by evaluation, not by the causal calibration module."""
import numpy as np
METHODS=('merton','naive','sundial','adapted','calibrated')

def score(window_id,path_id,kind,methods,labels):
 y=np.asarray(labels,dtype=float);rows=[];raw=[]
 for name in METHODS:
  x=np.asarray(methods[name],dtype=float);assert x.shape==(6,len(y))
  crps=float(np.mean(np.abs(x-y).mean(axis=0)-.5*np.abs(x[:,None]-x[None,:]).mean(axis=(0,1))))
  rows.append(dict(window_id=window_id,path_id=path_id,type=kind,method=name,crps=crps,mae=float(np.abs(x.mean(axis=0)-y).mean()),bias=float(np.mean(x.mean(axis=0)-y))))
  raw.append(dict(window_id=window_id,path_id=path_id,type=kind,method=name,samples=x.tolist(),labels=y.tolist()))
 return rows,raw

def aggregate(rows):
 paths=[]
 for pid in sorted({r['path_id'] for r in rows}):
  local=[r for r in rows if r['path_id']==pid];means={m:{k:float(np.mean([r[k] for r in local if r['method']==m])) for k in ('crps','mae','bias')} for m in METHODS}
  paths.append(dict(path_id=pid,type=local[0]['type'],means=means))
 def average(ps):return {m:{k:float(np.mean([p['means'][m][k] for p in ps])) for k in ('crps','mae','bias')} for m in METHODS}
 return dict(overall=average(paths),by_type={t:average([p for p in paths if p['type']==t]) for t in sorted({p['type'] for p in paths})},paths=paths,per_window=rows)
