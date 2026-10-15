"""Frozen-input infrastructure for a single API-free adapter experiment."""
import gzip,hashlib,importlib.util,json,os,subprocess,sys,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
OUT=ROOT/'results/sundial_multiscale_adapter/v1'
OLD=ROOT/'results/sundial_adapter_development/v1/best_adapter.json'
DOCS=[ROOT/'docs/superpowers/specs/2026-10-15-sundial-multiscale-adapter-design.md',ROOT/'docs/superpowers/plans/2026-10-15-sundial-multiscale-adapter.md']
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,value):Path(p).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as stream:
  while chunk:=stream.read(8*1024*1024):h.update(chunk)
 return h.hexdigest()
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
predictor=module('multiscale_frozen_predictor',ROOT/'experiments/sundial_closed_loop_development/predictor.py')
paths=module('multiscale_original_merton',ROOT/'experiments/timesfm_path_development/paths.py')
def trace_hash(trace):return hashlib.sha256(json.dumps(list(map(int,trace[:200])),separators=(',',':')).encode()).hexdigest()
def verify():
 for p,sha in read(OUT/'freeze.json')['sha256'].items():assert digest(p)==sha,p
def register():
 assert not OUT.exists(),'Do not overwrite any attempt'
 old=read(ROOT/'results/sundial_focus_completion/v1/freeze.json');hashes={str(ROOT/p):sha for p,sha in old['source_sha256'].items()}
 hashes.update(old['dependencies'])
 files=list(HERE.glob('*.py'))+DOCS+[OLD,Path(sys.executable)]
 hashes.update({str(p):digest(p) for p in files})
 for p,sha in hashes.items():assert digest(p)==sha,p
 OUT.mkdir(parents=True);write(OUT/'freeze.json',dict(sha256=hashes,revision=predictor.REVISION,api_budget=0,train_paths=120,dev_paths=30,windows=900,parameter_count=24,epochs_cap=200,training_variants=['crps24','multiscale24'],main_variant='multiscale24'))
 package=ROOT/'docs/artifacts/sundial_multiscale_adapter_preregistration_v1';assert not package.exists();package.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as environment:key=winreg.QueryValueEx(environment,'DEEPSEEK_API_KEY')[0].encode()
 entries={};files += [OUT/'freeze.json']
 for i,p in enumerate(files):
  if p==Path(sys.executable):continue
  raw=p.read_bytes();assert key not in raw;dest=package/'files'/f'{i:03d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 write(package/'manifest.json',dict(files=entries,api=0,checkpoint_weights_local_only=True,credential_absent=True))
 write(OUT/'publication.json',dict(files={**{p:v['gzip_sha256'] for p,v in entries.items()},(package/'manifest.json').relative_to(ROOT).as_posix():digest(package/'manifest.json')}))
 print('MULTISCALE_REGISTERED',len(entries),flush=True)
def published():
 verify();revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert revision==remote
 for path,sha in read(OUT/'publication.json')['files'].items():assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{path}'],cwd=ROOT)).hexdigest()==sha
 return revision
