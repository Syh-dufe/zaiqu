"""Download public, revision-pinned weights into an isolated cache."""
import hashlib
import json
import time
import urllib.request
from pathlib import Path

REVISION='1d952420fba87f3c6dee4f240de0f1a0fbc790e3'
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/timesfm_forecast_pilot/setup_v1'
CACHE=Path('C:/Users/13384/.cache/zaiqu-timesfm-pilot/model')/REVISION
OUT.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7890'}))
manifest={}
try:
    for name in ('config.json','model.safetensors'):
        url=f'https://huggingface.co/google/timesfm-2.5-200m-pytorch/resolve/{REVISION}/{name}'
        path=CACHE/name
        if path.exists():
            manifest[name]=dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest());continue
        with opener.open(url,timeout=60) as response, (CACHE/(name+'.part')).open('wb') as file:
            total=response.headers.get('Content-Length');h=hashlib.sha256();size=0;last=0
            while chunk:=response.read(8*1024*1024):
                file.write(chunk);h.update(chunk);size+=len(chunk)
                if time.monotonic()-last>10:
                    (OUT/'progress.json').write_text(json.dumps(dict(file=name,downloaded=size,total=total)),encoding='utf-8')
                    print(name,size,total,flush=True);last=time.monotonic()
        if name=='model.safetensors':assert size==925181104
        (CACHE/(name+'.part')).rename(path)
        manifest[name]=dict(bytes=size,sha256=h.hexdigest())
    (OUT/'download_completed.json').write_text(json.dumps(dict(revision=REVISION,cache=str(CACHE),files=manifest),indent=2),encoding='utf-8')
    print('DOWNLOAD_COMPLETE',flush=True)
except Exception as exc:
    (OUT/'download_failed.json').write_text(json.dumps(dict(error=type(exc).__name__,detail=str(exc))),encoding='utf-8')
    raise
