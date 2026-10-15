"""Causal bounded location response, one policy shared by every shock type."""
import numpy as np
CANDIDATES={'zero':(0.,0.,0.),'all_half':(.5,.5,.5),'up_half':(.5,0.,0.),'down_half':(0.,.5,0.),'change_half':(.5,.5,0.)}
def apply(samples,history,age,candidate):
 x=np.asarray(samples,dtype=np.float64);assert x.shape[0]==32 and age in (0,1,2) and candidate in CANDIDATES
 b=np.asarray(history,dtype=np.float64);assert len(b) and np.isfinite(b).all() and np.isfinite(x).all()
 prior=b[max(0,len(b)-11):-1]
 z=float((b[-1]-b[-4:-1].mean())/max(1.,float(prior.std()))) if len(b)>=4 else 0.
 state='up' if z>.5 else 'down' if z<-.5 else 'flat';index={'up':0,'down':1,'flat':2}[state]
 coefficient=CANDIDATES[candidate][index]*3/(3+age);mu=x.mean(0)
 shift=np.clip(coefficient*(b[-1]-mu),-4,4);y=np.clip(x+shift[None,:],0,20)
 return y,dict(candidate=candidate,state=state,z=z,coefficient=coefficient,last_report=float(b[-1]),report_age=age,block_shifts=shift.tolist(),base_means=mu.tolist())
