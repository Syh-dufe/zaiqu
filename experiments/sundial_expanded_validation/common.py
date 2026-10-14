"""New output scope and explicit immutable model/path dependencies."""
import hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
OUT=ROOT/'results/sundial_expanded_validation/v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
def module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);v=importlib.util.module_from_spec(spec);sys.modules[name]=v;spec.loader.exec_module(v);return v
pilot=module('sundial_frozen_pilot_functions',ROOT/'experiments/sundial_forecast_pilot/run.py')
paths=module('sundial_frozen_merton_paths',ROOT/'experiments/timesfm_path_development/paths.py')
def verify_freeze():
 f=read(OUT/'freeze.json')
 for p,sha in f['sha256'].items():assert digest(p)==sha,p
 return f
