"""One frozen CPU forecast pass over new inputs, no training or API."""
import math,os,sys,time
import numpy as np
from common import ROOT,OUT,read,write,digest,pilot,paths,verify_freeze

def run():
 verify_freeze();prepared=read(OUT/'prepared.json')
 assert digest(OUT/'cases.json')==prepared['cases_sha256'] and digest(OUT/'inputs.json')==prepared['inputs_sha256']
 with (OUT/'started.lock').open('x') as f:f.write('one registered forecast pass\n')
 sys.path.insert(0,str(pilot.DEPS));os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 try:
  import torch,hashlib
  from transformers import AutoModelForCausalLM
  torch.set_num_threads(2);start=time.perf_counter()
  model=AutoModelForCausalLM.from_pretrained(str(pilot.MODEL),trust_remote_code=True,local_files_only=True,torch_dtype=torch.float32)
  model.eval();assert next(model.parameters()).device.type=='cpu' and model.config.num_sampling_steps==50
  def parameter_hash():
   h=hashlib.sha256()
   for name,tensor in model.state_dict().items():h.update(name.encode());h.update(tensor.detach().cpu().numpy().tobytes())
   return h.hexdigest()
  before=parameter_hash();write(OUT/'model_loaded.json',dict(parameter_sha256=before,revision=pilot.REVISION,torch=torch.__version__,generation=model.generation_config.to_dict(),seconds=time.perf_counter()-start))
  results=[];inference=0
  for c in read(OUT/'cases.json'):
   blocks=c['block_history'];age=c['report_age'];assert len(blocks)*3+age==c['decision_period']-1
   count=math.ceil((age+20)/3);x=torch.tensor([blocks],dtype=torch.float32);streams=[];seeds=[];t=time.perf_counter()
   for purpose in ('search','review'):
    s=pilot.seed(c['id'],purpose);seeds.append(s);torch.manual_seed(s)
    with torch.inference_mode():v=model.generate(x,max_new_tokens=count,num_samples=16,revin=True)
    array=v.detach().cpu().numpy();assert array.shape==(1,16,count) and np.isfinite(array).all();streams.append(array[0])
   seconds=time.perf_counter()-t;inference+=seconds
   raw=np.concatenate(streams);bounded=np.clip(raw,0,20);aligned=np.repeat(bounded,3,axis=1)[:,age:age+20]
   merton=paths.generate([blocks[-1]]*20,blocks[-1],age,c['id'],original=True)
   results.append(dict(case_id=c['id'],raw_sundial_blocks=raw.tolist(),sundial_blocks=bounded.tolist(),sundial_period_paths=aligned.tolist(),sundial_seeds=seeds,merton=merton,seconds=seconds))
   write(OUT/'predictions.json',results);write(OUT/'progress.json',dict(status='running',cases=len(results),total=120))
   if len(results)%20==0:print('EXPANDED_CASES',len(results),flush=True)
  assert parameter_hash()==before
  verify_freeze();write(OUT/'run_finished.json',dict(cases=120,paths=20,parameters_unchanged=True,inference_seconds=inference,wall_seconds=time.perf_counter()-start,api=0,training=0))
 except Exception as exc:
  write(OUT/'failed.json',dict(error=type(exc).__name__,detail=str(exc),preserved=True));raise
if __name__=='__main__':run()
