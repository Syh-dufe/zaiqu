"""First registered Sundial generation attempt: causal report blocks only."""
import hashlib,json,math,os,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
OUT=ROOT/'results/sundial_forecast_pilot/development_v1'
DEPS=Path('C:/Users/13384/.cache/zaiqu-sundial-pilot/deps')
REVISION='3212e42564493f520593e5414af4367fc4b49226'
MODEL=Path('C:/Users/13384/.cache/zaiqu-sundial-pilot/model')/REVISION
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
def seed(case_id,purpose):return int.from_bytes(hashlib.sha256(f'sundial-pilot-v1|{case_id}|{purpose}'.encode()).digest()[:8],'big')%(2**63-1)
def run():
 assert not OUT.exists(),'Preserve previous attempt'
 setup=read(ROOT/'results/sundial_forecast_pilot/setup_v1/download_completed.json')
 assert setup['revision']==REVISION
 for n,e in setup['files'].items():assert digest(MODEL/n)==e['sha256']
 cases_path=ROOT/'results/timesfm_forecast_pilot/development_v1/cases.json'
 prior_path=ROOT/'results/timesfm_path_development/development_v1/paths.json'
 cases=read(cases_path);assert len(cases)==48 and len({c['id'] for c in cases})==48
 prior=read(prior_path);assert {r['case_id'] for r in prior}=={c['id'] for c in cases}
 files=list(HERE.glob('*.py'))+list(MODEL.glob('*'))+list(DEPS.rglob('*.py'))+list(DEPS.glob('*.dist-info/METADATA'))
 files += [cases_path,prior_path,ROOT/'docs/superpowers/specs/2026-10-14-sundial-pilot-design.md',ROOT/'docs/superpowers/plans/2026-10-14-sundial-pilot.md']
 OUT.mkdir(parents=True)
 write(OUT/'freeze.json',dict(sha256={str(p):digest(p) for p in files if p.is_file()},revision=REVISION,transformers='4.40.1',api=0,training=0,custom_code_inspected=True,checkpoint_local_only=True))
 (OUT/'started.lock').write_text('one registered attempt\n',encoding='utf-8')
 sys.path.insert(0,str(DEPS));os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
 try:
  import torch
  from transformers import AutoModelForCausalLM
  torch.set_num_threads(2);started=time.perf_counter()
  model=AutoModelForCausalLM.from_pretrained(str(MODEL),trust_remote_code=True,local_files_only=True,torch_dtype=torch.float32)
  model.eval();assert next(model.parameters()).device.type=='cpu'
  def parameters_hash():
   h=hashlib.sha256()
   for name,tensor in model.state_dict().items():h.update(name.encode());h.update(tensor.detach().cpu().numpy().tobytes())
   return h.hexdigest()
  before=parameters_hash()
  write(OUT/'model_loaded.json',dict(seconds=time.perf_counter()-started,torch=torch.__version__,parameters=sum(p.numel() for p in model.parameters()),sampling_steps=model.config.num_sampling_steps,generation_config=model.generation_config.to_dict(),parameter_sha256=before,source_revision=REVISION))
  records=[];times=[]
  for case in cases:
   blocks=case['block_history'];age=case['report_age'];count=math.ceil((age+20)/3)
   assert len(blocks)*3+age==case['decision_period']-1
   x=torch.tensor([blocks],dtype=torch.float32);streams=[];stream_seeds=[]
   t=time.perf_counter()
   for purpose in ('search','review'):
    s=seed(case['id'],purpose);stream_seeds.append(s);torch.manual_seed(s)
    with torch.inference_mode():output=model.generate(x,max_new_tokens=count,num_samples=16,revin=True)
    values=output.detach().cpu().numpy()
    assert values.shape==(1,16,count) and np.isfinite(values).all()
    streams.append(values[0])
   assert stream_seeds[0]!=stream_seeds[1]
   elapsed=time.perf_counter()-t;times.append(elapsed)
   raw=np.concatenate(streams);clipped=np.clip(raw,0,20);aligned=np.repeat(clipped,3,axis=1)[:,age:age+20]
   assert aligned.shape==(32,20)
   records.append(dict(case_id=case['id'],raw_blocks=raw.tolist(),blocks=clipped.tolist(),period_paths=aligned.tolist(),stream_seeds=stream_seeds,seconds=elapsed))
   write(OUT/'predictions.json',records);write(OUT/'progress.json',dict(cases=len(records),total_cases=48,api=0))
   if len(records)%8==0:print('SUNDIAL_CASES',len(records),flush=True)
  assert parameters_hash()==before
  write(OUT/'run_finished.json',dict(cases=48,api=0,training=0,inference_seconds=sum(times),wall_seconds=time.perf_counter()-started,parameters_unchanged=True))
 except Exception as exc:
  write(OUT/'failed.json',dict(error=type(exc).__name__,detail=str(exc),preserved=True));raise
if __name__=='__main__':run()
