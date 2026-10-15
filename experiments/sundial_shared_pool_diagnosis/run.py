"""Matched-state/union-candidate diagnostic, never a deployed future oracle."""
import argparse,gzip,hashlib,importlib.util,inspect,json,subprocess,sys,winreg
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=ROOT/'results/sundial_shared_pool_diagnosis/v1'
TRAIN=ROOT/'results/sundial_multiscale_adapter/v1';PROTOCOL=ROOT/'docs/superpowers/plans/2026-10-15-sundial-shared-pool-diagnosis.md'
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
locked=load('shared_pool_locked_replay',ROOT/'experiments/online_llm_artifacts/diagnose_sundial_double.py');read=locked.read;write=locked.write;digest=locked.core.digest
PROVIDERS=('original_merton','adapted_sundial','crps24','multiscale24')
def verify():
 for p,sha in read(OUT/'freeze.json')['sha256'].items():assert digest(Path(p))==sha,p
def register():
 assert not OUT.exists();assert read(TRAIN/'metrics.json')['gate_passed'] and read(TRAIN/'independent_audit.json')['status']=='passed'
 files=list(HERE.glob('*.py'))+[Path(locked.__file__),PROTOCOL,TRAIN/'crps24_best.json',TRAIN/'multiscale24_best.json',TRAIN/'metrics.json',TRAIN/'independent_audit.json']
 for seed in (14,15):files += [p for p in (ROOT/f'results/sundial_focus_completion/v1/runs/seed{seed}_two_types').rglob('*') if p.is_file()]
 hashes={str(ROOT/p):sha for p,sha in locked.core.source_hashes().items()};hashes.update({str(p):digest(p) for p in files})
 OUT.mkdir(parents=True);write(OUT/'freeze.json',dict(sha256=hashes,providers=PROVIDERS,api=0,shadow_branch_cap=1400,main_variant='multiscale24'))
 package=ROOT/'docs/artifacts/sundial_shared_pool_preregistration_v1';assert not package.exists();package.mkdir(parents=True)
 entries={}
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 for i,p in enumerate(files+[OUT/'freeze.json']):
  raw=p.read_bytes();assert key not in raw;dest=package/'files'/f'{i:03d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 write(package/'manifest.json',dict(files=entries,lossless=True,api=0,credential_absent=True));write(OUT/'publication.json',dict(files={**{p:v['gzip_sha256'] for p,v in entries.items()},(package/'manifest.json').relative_to(ROOT).as_posix():digest(package/'manifest.json')}))
 print('SHARED_POOL_REGISTERED',len(entries),flush=True)
def run(seed):
 verify();rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert rev==remote
 for p,sha in read(OUT/'publication.json')['files'].items():assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==sha
 with (OUT/f'seed{seed}.lock').open('x') as stream:stream.write(rev)
 weights={name:read(TRAIN/f'{name}_best.json')['weights'] for name in ('crps24','multiscale24')}
 def diagnostic_forecasts(provider,period,index):
  if provider in ('original_merton','adapted_sundial'):return index[provider,2,period]['forecasts']
  value=index['adapted_sundial',2,period]['forecast_audit'];prediction=value['prediction'];raw=np.clip(np.asarray(prediction['raw_blocks'],dtype=np.float64),0,20)
  features=locked.runner.predictor.correction.features(prediction['block_history'],raw,value['report_age']);selected=locked.runner.predictor.correction.transform(raw,features,weights[provider])
  result=locked.runner.predictor.allocate(selected,value['report_age'],value['horizon'],value['stream_identity'])['deployment'];return result[:3],result[3:]
 def canonical(value):
  if isinstance(value,np.ndarray):return value.tolist()
  if isinstance(value,np.generic):return value.item()
  raise TypeError(type(value).__name__)
 def state_hash(state,history,orders,proposed,recurrent):return hashlib.sha256(json.dumps(dict(state=state,history=history,orders=orders,proposed=proposed,recurrent=recurrent),sort_keys=True,separators=(',',':'),default=canonical).encode()).hexdigest()
 text=inspect.getsource(locked.run)
 before="for provider in runner.METHODS:\n      pair=index[provider,2,period]['forecasts']";assert text.count(before)==1
 text=text.replace(before,"for provider in PROVIDERS:\n      pair=diagnostic_forecasts(provider,period,index)")
 before="state=runner.original.snapshot(env,history);visible=reports.delivered_history.copy()";assert text.count(before)==1
 text=text.replace(before,before+"\n    result['state_sha256']=state_hash(state,visible,orders,proposed,recurrent)")
 namespace=dict(locked.__dict__,OUT=OUT,PROVIDERS=PROVIDERS,diagnostic_forecasts=diagnostic_forecasts,state_hash=state_hash)
 exec(compile(text,str(Path(__file__)),'exec'),namespace)
 try:namespace['run'](seed);verify()
 except Exception as error:write(OUT/f'seed{seed}_failed.json',dict(error=type(error).__name__,detail=str(error),preserved=True,api=0));raise
 print('SHARED_POOL_MATCHED_STATE_COMPLETE',seed,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run'));p.add_argument('--seed',type=int,choices=(14,15));a=p.parse_args();register() if a.action=='register' else run(a.seed)
