"""Fixed, causal compression of two independent 16-sample ensembles."""
import numpy as np

def select(paths):
 a=np.asarray(paths)
 if a.ndim!=2 or a.shape[0]!=32 or not 1<=a.shape[1]<=20:raise ValueError('Expected32 paths of horizon1..20')
 if not np.isfinite(a).all() or not np.equal(a,np.floor(a)).all() or (a<0).any() or (a>20).any():raise ValueError('Bounded integer paths required')
 horizon=a.shape[1];lengths=np.array([min(5,horizon),min(10,horizon),horizon])
 features=np.cumsum(a,axis=1)[:,lengths-1]/lengths[None,:]
 indices=[];layers=[]
 for offset in (0,16):
  order=sorted(range(offset,offset+16),key=lambda i:(int(a[i].sum()),i))
  for lo,hi in ((0,5),(5,11),(11,16)):
   members=order[lo:hi];center=features[members].mean(axis=0)
   chosen=min(members,key=lambda i:(float(np.square(features[i]-center).sum()),i))
   indices.append(chosen);layers.append(dict(members=members,selected=chosen,total=int(a[chosen].sum())))
 return [a[i].astype(int).tolist() for i in indices],dict(indices=indices,layers=layers,variant='stratified_representative_v1',equal_weight_approximation=True)
