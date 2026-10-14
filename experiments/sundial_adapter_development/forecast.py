import argparse,math,os,sys,time,hashlib
import numpy as np
from common import OUT,read,write,digest,pilot,paths,verify_freeze
def run(phase):
 verify_freeze();prepared=read(OUT/('prepared.json' if phase=='development' else 'test_prepared.json'))
 assert digest(OUT/f'{phase}_cases.json')==prepared['cases_sha256']
 with (OUT/f'{phase}_forecast.lock').open('x') as f:f.write('one frozen-model inference attempt\n')
 sys.path.insert(0,str(pilot.DEPS));os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 import torch
 from transformers import AutoModelForCausalLM
 torch.set_num_threads(2);started=time.perf_counter()
 model=AutoModelForCausalLM.from_pretrained(str(pilot.MODEL),trust_remote_code=True,local_files_only=True,torch_dtype=torch.float32);model.eval()
 def parameter_hash():
  h=hashlib.sha256()
  for n,t in model.state_dict().items():h.update(n.encode());h.update(t.detach().cpu().numpy().tobytes())
  return h.hexdigest()
 before=parameter_hash();records=[]
 try:
  for c in read(OUT/f'{phase}_cases.json'):
   blocks=c['block_history'];age=c['report_age'];assert len(blocks)*3+age==c['decision_period']-1
   count=math.ceil((age+20)/3);x=torch.tensor([blocks],dtype=torch.float32);streams=[];seeds=[]
   for purpose in ('search','review'):
    seed=pilot.seed(c['id'],purpose);seeds.append(seed);torch.manual_seed(seed)
    with torch.inference_mode():v=model.generate(x,max_new_tokens=count,num_samples=16,revin=True)
    a=v.detach().cpu().numpy();assert a.shape==(1,16,count) and np.isfinite(a).all();streams.append(a[0])
   raw=np.concatenate(streams);bounded=np.clip(raw,0,20)
   records.append(dict(case_id=c['id'],raw_blocks=raw.tolist(),blocks=bounded.tolist(),seeds=seeds,
     merton=paths.generate([blocks[-1]]*20,blocks[-1],age,c['id'],original=True),
     naive=paths.generate([blocks[-1]]*20,blocks[-1],age,c['id'])))
   write(OUT/f'{phase}_predictions.json',records)
   if len(records)%24==0:print(phase,'FORECAST_CASES',len(records),flush=True)
  assert parameter_hash()==before;verify_freeze()
  write(OUT/f'{phase}_forecast_completed.json',dict(cases=len(records),model_before=before,model_after=before,parameters_unchanged=True,wall_seconds=time.perf_counter()-started,api=0))
 except Exception as exc:write(OUT/f'{phase}_failed.json',dict(error=type(exc).__name__,detail=str(exc),preserved=True));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=('development','test'));run(p.parse_args().phase)
