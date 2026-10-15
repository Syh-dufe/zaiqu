"""One registered frozen-model forecast pass and two24-parameter optimizations."""
import argparse,gzip,hashlib,math,os,socket,sys,time,traceback,winreg
import numpy as np
from common import ROOT,HERE,OUT,OLD,DOCS,read,write,digest,verify,register,published,predictor,paths
from prepare import prepare,BACKGROUNDS,TYPES

def progress(stage,**values):write(OUT/'progress.json',dict(stage=stage,api=0,**values))
def inference(cases):
 import torch
 net=predictor.model();before=predictor.parameter_hash();records=[];started=time.perf_counter()
 def forbidden(*args,**kwargs):raise RuntimeError('Network forbidden in registered local experiment')
 socket.socket=forbidden
 for case in cases:
  history=case['block_history'];count=math.ceil((case['report_age']+20)/3)
  raw,seeds=predictor.sample_blocks(history,count,case['id'])
  assert raw.shape==(32,count) and np.isfinite(raw).all()
  records.append(dict(case_id=case['id'],raw_blocks=raw.tolist(),sampling_seeds=seeds))
  if len(records)%30==0 or len(records)==len(cases):
   write(OUT/'predictions.json',records);progress('forecast',completed_windows=len(records),total_windows=len(cases),seconds=time.perf_counter()-started)
   print('MULTISCALE_FORECAST',len(records),len(cases),flush=True)
 after=predictor.parameter_hash();assert before==after
 write(OUT/'model_verification.json',dict(before=before,after=after,parameters_unchanged=True,sundial_updates=0,happo_updates=0))
 verify();return records

def arrays(cases,predictions,split):
 lookup={r['case_id']:r for r in predictions};chosen=[c for c in cases if c['split']==split]
 counts={pid:sum(c['path_id']==pid for c in chosen) for pid in {c['path_id'] for c in chosen}};assert set(counts.values())=={6}
 xs=[];fs=[];ys=[];masks=[];valids=[];ages=[];labels=[]
 for c in chosen:
  a=np.clip(np.asarray(lookup[c['id']]['raw_blocks'],dtype=np.float64),0,20);n=a.shape[1]
  f=predictor.correction.features(c['block_history'],a,c['report_age']);x=np.zeros((32,8));x[:,:n]=a;feature=np.zeros((8,8));feature[:n]=f
  y=np.zeros(8);mask=np.zeros(8);valid=np.zeros(8);valid[:n]=1
  for j in range(n):
   start=j*3-c['report_age']
   if 0<=start and start+3<=20:y[j]=np.mean(c['future_label'][start:start+3]);mask[j]=1
  xs.append(x);fs.append(feature);ys.append(y);masks.append(mask);valids.append(valid);ages.append(c['report_age']);labels.append(c['future_label'])
 return dict(x=np.array(xs),f=np.array(fs),y=np.array(ys),mask=np.array(masks),valid=np.array(valids),age=np.array(ages),labels=np.array(labels))

def train(cases,predictions):
 import torch
 torch.set_num_threads(2);torch.manual_seed(20272251);initial=read(OLD)['weights'];fitted={}
 data={split:{k:torch.tensor(v,dtype=torch.int64 if k=='age' else torch.float64) for k,v in arrays(cases,predictions,split).items()} for split in ('train','dev')}
 def crps(v,y):
  n=v.shape[1];coeff=torch.arange(n,dtype=torch.float64)*2+1-n
  return (v-y[:,None,:]).abs().mean(1)-(v.sort(dim=1).values*coeff[None,:,None]).sum(1)/n**2
 for name in ('crps24','multiscale24'):
  parameters={k:torch.nn.Parameter(torch.tensor(initial[k],dtype=torch.float64)) for k in ('wb','wa','wg')}
  optimizer=torch.optim.Adam(list(parameters.values()),lr=.01);curve=[];stale=0;best=math.inf;best_epoch=0;best_weights=None
  def loss(split):
   d=data[split];x=d['x'];f=d['f'];mu=x.mean(1);g=torch.sigmoid(f@parameters['wg']);b=6*torch.tanh(f@parameters['wb']);a=torch.exp(math.log(4)*torch.tanh(f@parameters['wa']))
   z=(mu[:,None,:]+(g*b)[:,None,:]+(1+g*(a-1))[:,None,:]*(x-mu[:,None,:])).clamp(0,20)
   block=(crps(z,d['y'])*d['mask']).sum(1)/d['mask'].sum(1)
   unfolded=z.repeat_interleave(3,dim=2);idx=d['age'][:,None,None]+torch.arange(20)[None,None,:];periods=torch.gather(unfolded,2,idx.expand(-1,32,-1))
   horizons=torch.tensor([5,10,20],dtype=torch.float64);prefix=periods.cumsum(2)[:,:,[4,9,19]]/horizons[None,None,:];truth=d['labels'].cumsum(1)[:,[4,9,19]]/horizons[None,:]
   prefix_loss=crps(prefix,truth).mean(1);adjustment=((z-x).abs().mean(1)*d['valid']).sum(1)/d['valid'].sum(1)
   regularizer=.001*(parameters['wb'].square().mean()+parameters['wa'].square().mean())
   total=block.mean()+regularizer
   if name=='multiscale24':total=total+.25*prefix_loss.mean()+.05*adjustment.mean()
   return total,dict(block_crps=float(block.mean().detach()),proxy_prefix_crps=float(prefix_loss.mean().detach()),mean_adjustment=float(adjustment.mean().detach()))
  for epoch in range(201):
   if epoch:
    optimizer.zero_grad();value,_=loss('train');value.backward();optimizer.step()
   with torch.no_grad():tr,tm=loss('train');dv,dm=loss('dev')
   assert torch.isfinite(tr) and torch.isfinite(dv)
   curve.append(dict(epoch=epoch,train_objective=float(tr),dev_objective=float(dv),train=tm,dev=dm))
   weights={k:v.detach().numpy().tolist() for k,v in parameters.items()}
   if float(dv)<best:best=float(dv);best_epoch=epoch;best_weights=weights;stale=0
   else:stale+=1
   if stale>=25:break
  assert best_weights is not None
  fitted[name]=dict(weights=best_weights,selected_epoch=best_epoch,dev_objective=best,parameter_count=24,initialization_sha256=digest(OLD),dtype='float64',actual_algorithm='gated_location_scale_'+name)
  write(OUT/f'{name}_curve.json',curve);write(OUT/f'{name}_best.json',fitted[name]);write(OUT/f'{name}_final.json',dict(weights=weights,epoch=epoch,dev_objective=curve[-1]['dev_objective'],stop_reason='patience25' if stale>=25 else 'max200'))
  progress('fit',variant=name,epochs=epoch,selected_epoch=best_epoch);print('MULTISCALE_FIT',name,best_epoch,best,flush=True)
 verify();return fitted

def crps(x,y):
 x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float);n=x.shape[0]
 first=(np.abs(x-y[None,:]).mean(0)-.5*np.abs(x[:,None,:]-x[None,:,:]).mean((0,1))).mean()
 second=(np.abs(x-y[None,:]).mean(0)-((2*np.arange(n)+1-n)[:,None]*np.sort(x,axis=0)).sum(0)/n**2).mean()
 assert abs(first-second)<1e-10;return float(first)

def evaluate(cases,predictions,fitted):
 lookup={r['case_id']:r for r in predictions};old=read(OLD)['weights'];rows=[];scoring=[]
 for c in [c for c in cases if c['split']=='dev']:
  raw=np.clip(np.asarray(lookup[c['id']]['raw_blocks'],dtype=np.float32),0,20);canonical=raw.astype(np.float64);features=predictor.correction.features(c['block_history'],canonical,c['report_age'])
  blocks={'native_sundial':raw,'old24':predictor.correction.transform(raw,predictor.correction.features(c['block_history'],raw,c['report_age']),old)}
  for name,value in fitted.items():blocks[name]=predictor.correction.transform(canonical,features,value['weights'])
  age=c['report_age'];starts=[s for s in range(-age,20,3) if s>=0 and s+3<=20];indices=[(s+age)//3 for s in starts]
  labels=np.asarray(c['future_label']);block_labels=np.array([labels[s:s+3].mean() for s in starts]);prefix_labels=np.cumsum(labels)[[4,9,19]]/np.array([5,10,20]);methods={}
  for name,x in blocks.items():
   allocated=np.asarray(predictor.allocate(x,age,20,c['id'])['paths']);prefix=np.cumsum(allocated,axis=1)[:,[4,9,19]]/np.array([5,10,20])
   proxy=np.repeat(x,3,axis=1)[:,age:age+20];proxy_prefix=np.cumsum(proxy,axis=1)[:,[4,9,19]]/np.array([5,10,20])
   methods[name]=(x[:,indices],prefix,proxy_prefix)
  last=c['block_history'][-1];merton=np.asarray(paths.generate([last]*20,last,age,c['id'],original=True)['paths']);naive=np.full((32,20),last)
  for name,x in (('merton',merton),('latest_report',naive)):
   block=np.stack([x[:,s:s+3].mean(1) for s in starts],axis=1);prefix=np.cumsum(x,axis=1)[:,[4,9,19]]/np.array([5,10,20]);methods[name]=(block,prefix,prefix)
  for name,(block,prefix,proxy) in methods.items():
   rows.append(dict(case_id=c['id'],path_id=c['path_id'],background=c['background'],type=c['type'],method=name,block_crps=crps(block,block_labels),block_mae=float(np.abs(block.mean(0)-block_labels).mean()),prefix_crps=crps(prefix,prefix_labels),proxy_prefix_crps=crps(proxy,prefix_labels)))
   scoring.append(dict(case_id=c['id'],method=name,block_samples=block.tolist(),block_labels=block_labels.tolist(),prefix_samples=prefix.tolist(),prefix_labels=prefix_labels.tolist()))
 path_rows=[];names=list(methods)
 for pid in sorted({r['path_id'] for r in rows}):
  local=[r for r in rows if r['path_id']==pid];assert len(local)==36
  path_rows.append(dict(path_id=pid,background=local[0]['background'],type=local[0]['type'],metrics={m:{k:float(np.mean([r[k] for r in local if r['method']==m])) for k in ('block_crps','block_mae','prefix_crps','proxy_prefix_crps')} for m in names}))
 def mean(ps):return {m:{k:float(np.mean([p['metrics'][m][k] for p in ps])) for k in ('block_crps','block_mae','prefix_crps','proxy_prefix_crps')} for m in names}
 overall=mean(path_rows);by_type={t:mean([p for p in path_rows if p['type']==t]) for t in TYPES};new=overall['multiscale24']
 checks=dict(block_better_than_old=new['block_crps']<overall['old24']['block_crps'],prefix_better_than_old=new['prefix_crps']<overall['old24']['prefix_crps'],prefix_better_than_merton=new['prefix_crps']<overall['merton']['prefix_crps'],prefix_better_than_latest=new['prefix_crps']<overall['latest_report']['prefix_crps'],no_shock_type_above_old_5_percent=all(by_type[t]['multiscale24']['prefix_crps']<=1.05*by_type[t]['old24']['prefix_crps'] for t in TYPES if t!='normal'))
 result=dict(overall=overall,by_type=by_type,by_background={b:mean([p for p in path_rows if p['background']==b]) for b in BACKGROUNDS},paths=path_rows,per_case=rows,gate_checks=checks,gate_passed=all(checks.values()),independent_paths=30,overlapping_windows=180,api=0,no_new_inventory_cost_results=True)
 write(OUT/'metrics.json',result);write(OUT/'scoring_values.json',scoring);verify();return result

def archive():
 package=OUT/'archive';assert not package.exists();package.mkdir();entries={}
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as environment:key=winreg.QueryValueEx(environment,'DEEPSEEK_API_KEY')[0].encode()
 for p in list(OUT.rglob('*')):
  if not p.is_file() or package in p.parents:continue
  raw=p.read_bytes();assert key not in raw;dest=package/(p.relative_to(OUT).as_posix()+'.gz');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw;entries[str(dest.relative_to(package))]=dict(source_sha256=digest(p),gzip_sha256=digest(dest))
 write(package/'manifest.json',dict(files=entries,lossless=True,api=0,credential_absent=True))

def run():
 revision=published()
 with (OUT/'started.lock').open('x') as stream:stream.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),revision=revision));started=time.perf_counter()
 try:
  progress('prepare');prepare();cases=read(OUT/'cases.json');predictions=inference(cases);fitted=train(cases,predictions);progress('evaluate');result=evaluate(cases,predictions,fitted)
  verify();write(OUT/'completed.json',dict(api=0,train_paths=120,dev_paths=30,windows=900,gate_passed=result['gate_passed'],next_stage='register_shared_candidate_diagnosis' if result['gate_passed'] else 'stop_this_version',wall_seconds=time.perf_counter()-started,adapter_updates_only=True,old_adapter_sha256=digest(OLD)))
  progress('completed',gate_passed=result['gate_passed']);archive();print('MULTISCALE_COMPLETED',result['gate_checks'],result['overall'],flush=True)
 except Exception as error:write(OUT/'failed.json',dict(error=type(error).__name__,detail=str(error),preserved=True,api=0));traceback.print_exc();raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run','verify'));a=p.parse_args();{'register':register,'run':run,'verify':verify}[a.action]()
