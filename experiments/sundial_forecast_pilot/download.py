"""Public revision-pinned Sundial weights and auditable custom code."""
import hashlib,json,time,urllib.request
from pathlib import Path
REVISION='3212e42564493f520593e5414af4367fc4b49226'
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/sundial_forecast_pilot/setup_v1'
CACHE=Path('C:/Users/13384/.cache/zaiqu-sundial-pilot/model')/REVISION
OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7890'}))
files={}
try:
 for name in ('README.md','config.json','configuration_sundial.py','flow_loss.py','generation_config.json','modeling_sundial.py','ts_generation_mixin.py','model.safetensors'):
  path=CACHE/name
  if path.exists():files[name]=dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest());continue
  h=hashlib.sha256();size=0;last=0
  with opener.open(f'https://huggingface.co/thuml/sundial-base-128m/resolve/{REVISION}/{name}',timeout=60) as response,(CACHE/(name+'.part')).open('xb') as f:
   while chunk:=response.read(8*1024*1024):
    f.write(chunk);h.update(chunk);size+=len(chunk)
    if time.monotonic()-last>10:
     (OUT/'progress.json').write_text(json.dumps(dict(file=name,bytes=size)),encoding='utf-8');print(name,size,flush=True);last=time.monotonic()
  (CACHE/(name+'.part')).rename(path);files[name]=dict(bytes=size,sha256=h.hexdigest())
 (OUT/'download_completed.json').write_text(json.dumps(dict(revision=REVISION,cache=str(CACHE),files=files),indent=2),encoding='utf-8')
 print('SUNDIAL_DOWNLOAD_COMPLETE',flush=True)
except Exception as exc:
 (OUT/'failed.json').write_text(json.dumps(dict(error=type(exc).__name__,detail=str(exc))),encoding='utf-8');raise
