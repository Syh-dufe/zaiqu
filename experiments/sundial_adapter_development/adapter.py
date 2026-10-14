import numpy as np
def features(blocks,samples,age):
 mu=np.mean(samples,axis=0);recent=np.asarray(blocks[-3:],dtype=float);x=np.arange(len(recent),dtype=float)
 slope=float(np.dot(x-x.mean(),recent-recent.mean())/np.dot(x-x.mean(),x-x.mean())) if len(recent)>1 else 0
 return np.asarray([[1,m/20,blocks[-1]/20,(recent.mean()-np.mean(blocks[-10:]))/20,slope/20,np.std(blocks[-5:])/10,(j+1)/8,age/2] for j,m in enumerate(mu)],dtype=float)
def transform(samples,f,weights):
 mu=samples.mean(axis=0);g=1/(1+np.exp(-np.clip(f@np.asarray(weights['wg']),-700,700)))
 b=6*np.tanh(f@np.asarray(weights['wb']));a=np.exp(np.log(4)*np.tanh(f@np.asarray(weights['wa'])))
 return np.clip(mu+g*b+(1+g*(a-1))*(samples-mu),0,20)
def frames(cases,predictions):
 lookup={r['case_id']:r for r in predictions};xs=[];fs=[];ys=[];ws=[]
 for c in cases:
  a=np.asarray(lookup[c['id']]['blocks'],dtype=float);f=features(c['block_history'],a,c['report_age']);y=c['future_label']
  starts=[s for s in range(-c['report_age'],20,3) if 0<=s and s+3<=20]
  for s in starts:
   j=(s+c['report_age'])//3;xs.append(a[:,j]);fs.append(f[j]);ys.append(sum(y[s:s+3])/3);ws.append(1/len(starts)/len(cases))
 return np.asarray(xs),np.asarray(fs),np.asarray(ys),np.asarray(ws)
