import time
import numpy as np
import torch
from common import OUT,read,write,digest,verify_freeze
from adapter import frames
def fit():
 verify_freeze();assert not (OUT/'fit.lock').exists()
 (OUT/'fit.lock').write_text('one registered adapter optimization\n',encoding='utf-8')
 torch.set_num_threads(2);torch.manual_seed(20261015);start=time.perf_counter()
 cases=read(OUT/'development_cases.json');pred=read(OUT/'development_predictions.json')
 data={s:tuple(torch.tensor(a,dtype=torch.float64) for a in frames([c for c in cases if c['split']==s],pred)) for s in ('train','dev')}
 wb=torch.nn.Parameter(torch.zeros(8,dtype=torch.float64));wa=torch.nn.Parameter(torch.zeros(8,dtype=torch.float64));wg=torch.nn.Parameter(torch.tensor([-2.]+[0.]*7,dtype=torch.float64))
 opt=torch.optim.Adam([wb,wa,wg],lr=.01)
 coeff=torch.arange(32,dtype=torch.float64)*2-31
 def predict(x,f):
  mu=x.mean(dim=1);g=torch.sigmoid(f@wg);b=6*torch.tanh(f@wb);a=torch.exp(np.log(4)*torch.tanh(f@wa))
  return (mu[:,None]+(g*b)[:,None]+(1+g*(a-1))[:,None]*(x-mu[:,None])).clamp(0,20)
 def score(s):
  x,f,y,w=data[s];v=predict(x,f);ordered=v.sort(dim=1).values
  return ((torch.abs(v-y[:,None]).mean(dim=1)-(ordered*coeff).sum(dim=1)/1024)*w).sum()
 def weights():return {n:v.detach().numpy().tolist() for n,v in [('wb',wb),('wa',wa),('wg',wg)]}
 with torch.no_grad():best=float(score('dev'));initial_train=float(score('train'))
 best_epoch=0;best_weights=weights();curve=[dict(epoch=0,train_crps=initial_train,dev_crps=best)];stale=0
 for epoch in range(1,201):
  opt.zero_grad();loss=score('train')+.001*(wb.square().mean()+wa.square().mean());loss.backward();opt.step()
  with torch.no_grad():train=float(score('train'));dev=float(score('dev'))
  curve.append(dict(epoch=epoch,train_crps=train,dev_crps=dev))
  if dev<best:best=dev;best_epoch=epoch;best_weights=weights();stale=0
  else:stale+=1
  if stale>=25:break
 write(OUT/'fit_curve.json',curve);write(OUT/'best_adapter.json',dict(weights=best_weights,selected_epoch=best_epoch,dev_crps=best,actual_algorithm='offline_gated_location_scale_adapter',parameter_count=24))
 write(OUT/'final_adapter.json',dict(weights=weights(),epoch=epoch,dev_crps=curve[-1]['dev_crps']))
 verify_freeze();write(OUT/'fit_completed.json',dict(parameter_count=24,epochs=epoch,selected_epoch=best_epoch,initial_dev_crps=curve[0]['dev_crps'],best_dev_crps=best,best_sha256=digest(OUT/'best_adapter.json'),wall_seconds=time.perf_counter()-start,stop_reason='patience25' if stale>=25 else 'max200',sundial_updates=0,happo_updates=0,api=0))
 print('ADAPTER_FIT_COMPLETED',best_epoch,best,flush=True)
if __name__=='__main__':fit()
