"""Registered public Merton innovations; no realized future argument."""
import hashlib
import numpy as np

def stream_seed(identity, purpose):
    value='timesfm-path-v1|'+identity+'|'+purpose
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8],'big')

def generate(center, last_report, age, identity, original=False):
    center=np.asarray(center,dtype=float)
    assert center.ndim==1 and 1<=len(center)<=20 and age in (0,1,2)
    assert np.isfinite(center).all() and ((center>=0)&(center<=20)).all()
    outputs=[]; continuous=[]; seeds=[]
    for purpose in ('search','review'):
        seed=stream_seed(identity,purpose);seeds.append(seed)
        rng=np.random.default_rng(seed)
        w=np.zeros(16); raw=[]
        for step in range(age+len(center)):
            z=rng.normal(0,1,16);n=rng.poisson(15,16);z2=rng.normal(0,2,16)
            w+=np.sqrt(15)*.01*z+.01*np.sqrt(n)*z2
            if step<age:continue
            j=step-age
            if original:
                x=np.exp(np.clip(np.log(last_report+.5)+w,-20,20))
            else:
                x=(center[j]+.5)*np.exp(w-.5*.0075*(step+1))-.5
            raw.append(x.copy())
        raw=np.stack(raw,axis=1)
        integers=np.floor(np.clip(raw,0,20)+(0 if original else .5)).astype(int)
        continuous.append(raw);outputs.append(integers)
    assert seeds[0]!=seeds[1]
    values=np.concatenate(outputs);raw=np.concatenate(continuous)
    deployment=np.concatenate([outputs[0][:3],outputs[1][:3]])
    return dict(paths=values.tolist(),raw=raw.tolist(),deployment=deployment.tolist(),stream_seeds=seeds)
