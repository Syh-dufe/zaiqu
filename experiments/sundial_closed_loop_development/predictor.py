"""Frozen Sundial block distributions and declared integer period allocation."""
import hashlib,importlib.util,math,os,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
DEPS=Path('C:/Users/13384/.cache/zaiqu-sundial-pilot/deps')
REVISION='3212e42564493f520593e5414af4367fc4b49226'
MODEL=Path('C:/Users/13384/.cache/zaiqu-sundial-pilot/model')/REVISION
ADAPTER=ROOT/'results/sundial_adapter_development/v1/best_adapter.json'
_model=None
spec=importlib.util.spec_from_file_location('sundial_closed_loop_frozen_transform',ROOT/'experiments/sundial_adapter_development/adapter.py')
correction=importlib.util.module_from_spec(spec);spec.loader.exec_module(correction)

def stream_seed(identity,purpose):
 return int.from_bytes(hashlib.sha256(f'sundial-closed-loop-v1|{identity}|{purpose}'.encode()).digest()[:8],'big')%(2**63-1)

def model():
 global _model
 if _model is None:
  sys.path.insert(0,str(DEPS));os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
  import torch
  from transformers import AutoModelForCausalLM
  torch.set_num_threads(2)
  _model=AutoModelForCausalLM.from_pretrained(str(MODEL),trust_remote_code=True,local_files_only=True,torch_dtype=torch.float32)
  _model.eval();assert next(_model.parameters()).device.type=='cpu'
 return _model

def parameter_hash():
 h=hashlib.sha256()
 for name,t in model().state_dict().items():h.update(name.encode());h.update(t.detach().cpu().numpy().tobytes())
 return h.hexdigest()

def sample_blocks(blocks,count,identity):
 import torch
 net=model();previous=torch.get_num_threads();torch.set_num_threads(2)
 x=torch.tensor([blocks],dtype=torch.float32);values=[];seeds=[]
 try:
  for purpose in ('search','review'):
   seed=stream_seed(identity,purpose);seeds.append(seed);torch.manual_seed(seed)
   with torch.inference_mode():a=net.generate(x,max_new_tokens=count,num_samples=16,revin=True)
   a=a.detach().cpu().numpy();assert a.shape==(1,16,count) and np.isfinite(a).all();values.append(a[0])
 finally:torch.set_num_threads(previous)
 return np.concatenate(values),seeds

def allocate(blocks,age,horizon,identity):
 blocks=np.asarray(blocks,dtype=float);assert blocks.shape==(32,math.ceil((age+horizon)/3))
 rows=[];totals=[];seeds=[]
 for index,x in enumerate(blocks):
  purpose='search' if index<16 else 'review';draw=index%16
  seed=stream_seed(identity,f'allocate_{purpose}_{draw}');seeds.append(seed);rng=np.random.default_rng(seed)
  uniforms=rng.random((len(x),60));values=[];row_totals=[]
  for j,m in enumerate(x):
   total=int(math.floor(3*float(np.clip(m,0,20))+.5));counts=[0,0,0]
   for u in uniforms[j,:total]:
    available=[k for k,v in enumerate(counts) if v<20]
    counts[available[min(len(available)-1,int(float(u)*len(available)))]]+=1
   assert sum(counts)==total and all(0<=v<=20 for v in counts)
   row_totals.append(total);values.extend(counts)
  rows.append(values[age:age+horizon]);totals.append(row_totals)
 assert all(len(v)==horizon for v in rows)
 return dict(paths=rows,deployment=[rows[i] for i in (0,1,2,16,17,18)],totals=totals,allocation_seeds=seeds)

class Centers:
 def __init__(self):self.cache={}
 def forecast(self,history,age,horizon,identity,adapted):
  assert len(history)%3==0 and age in (0,1,2) and 1<=horizon<=20
  blocks=[]
  for i in range(0,len(history),3):
   assert history[i]==history[i+1]==history[i+2];blocks.append(float(history[i]))
  count=math.ceil((age+horizon)/3);key=(tuple(blocks),count,identity);started=time.perf_counter();hit=key in self.cache
  if not hit:self.cache[key]=sample_blocks(blocks,count,identity)
  raw,seeds=self.cache[key];bounded=np.clip(raw,0,20);weights=__import__('json').loads(ADAPTER.read_text(encoding='utf-8'))['weights']
  selected=correction.transform(bounded,correction.features(blocks,bounded,age),weights) if adapted else bounded
  value=allocate(selected,age,horizon,identity)
  return value,dict(block_history=blocks,raw_blocks=raw.tolist(),selected_blocks=selected.tolist(),sampling_seeds=seeds,
    cache_hit=hit,seconds=time.perf_counter()-started,revision=REVISION,adapter_sha256=hashlib.sha256(ADAPTER.read_bytes()).hexdigest(),
    adapted=adapted,allocation_totals=value['totals'],allocation_seeds=value['allocation_seeds'],diagnostic_paths=value['paths'])
