"""Explicit module loading and protected experiment IO."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
OUTPUT=ROOT/'results/submission_required/v1'
SEEDS=(11,12,13,14,15)
TYPES=('single_surge','sustained_surge','double_surge','surge_then_drop')
METHODS=('happo','online_feedback','no_feedback','no_review','first_only','deterministic_search')
PYTHON=Path('C:/Users/13384/.codex/worktrees/delivery-happo/新/.venv/Scripts/python.exe')

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value)
    return value

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(value,ensure_ascii=False,indent=2)
    key=os.environ.get('DEEPSEEK_API_KEY')
    if key:text=text.replace(key,'[REDACTED]')
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(text,encoding='utf-8');os.replace(tmp,path)

def key_from_user():
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:
        key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0]
    if not key:raise RuntimeError('User API credential unavailable')
    os.environ['DEEPSEEK_API_KEY']=key
    # Keep the historical deployment name, not a new default selected by results.
    os.environ['DEEPSEEK_MODEL']='deepseek-flash'

def training(seed):
    return ROOT/'results/learning_curve'/('curve_seed11_until_stable_v1' if seed==11 else f'curve_seed{seed}_formal_v1')

def calls_under(path):
    calls=[]
    for p in sorted(Path(path).rglob('calls.json')):
        calls.extend(dict(source=str(p),**x) for x in read(p))
    return calls

def usage(calls):
    result={}
    for c in calls:
        for k,v in (c.get('usage') or {}).items():
            if type(v) in (int,float):result[k]=result.get(k,0)+v
    return result
