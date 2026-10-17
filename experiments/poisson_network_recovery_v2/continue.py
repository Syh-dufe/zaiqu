"""Preserve v1 offline failure; correct input and subprocess root mappings only."""
import argparse
import importlib.util
import inspect
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
source=ROOT/'experiments/poisson_network_recovery/continue.py'
spec=importlib.util.spec_from_file_location('poisson_immutable_network_continuation',source)
base=importlib.util.module_from_spec(spec);sys.modules[spec.name]=base;spec.loader.exec_module(base)
FIRST=base.OUT
OLD_PLAN=base.PLAN
base.OUT=ROOT/'results/poisson_full_mechanism/network_recovery_v2'
base.HERE=HERE
base.PLAN=ROOT/'docs/superpowers/plans/2026-10-17-poisson-network-recovery-v2.md'
setup_original=base.setup

def setup(lead,seed,offline=False):
    setup_original(lead,seed,offline)
    if offline:
        base.r.OUT.mkdir(parents=True,exist_ok=True)
        target=base.r.OUT/'inputs.json'
        assert not target.exists()
        target.write_bytes((base.OUT/'inputs.json').read_bytes())
base.setup=setup

def prepare():
    base.prepare()
    reg=base.read(base.OUT/'registration.json')
    paths=[source,OLD_PLAN,*[p for p in FIRST.rglob('*') if p.is_file()]]
    for p in paths:reg['files'][p.relative_to(ROOT).as_posix()]=base.sha(p)
    reg['preparation_only_failure']='v1 offline replay missing copied input; zero new HTTP'
    base.write(base.OUT/'registration.json',reg)

def preflight():
    base.verify()
    with (base.OUT/'replay_preflight.log').open('x',encoding='utf-8') as log:
        subprocess.run([sys.executable,'-u',str(__file__),'worker','--lead','2','--seed','11','--offline'],
                       cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    assert base.read(base.OUT/'replay_preflight.json')['passed']
    files=[ROOT/p for p in base.read(base.OUT/'registration.json')['files'] if ROOT in (ROOT/p).parents]
    files.extend(p for p in base.OUT.rglob('*') if p.is_file())
    base.r.ref.archive(ROOT/'docs/artifacts/poisson_network_recovery_v2_preregistration',files)
    print('RECOVERY_V2_PREFLIGHT_PASSED',flush=True)

# Preserve dispatch and accounting verbatim, mapping only the new child entrypoint.
text=inspect.getsource(base.run)
assert text.count('str(__file__)')==1
text=text.replace('str(__file__)','str(HERE/"continue.py")')
namespace=dict(base.__dict__)
exec(compile(text,str(__file__),'exec'),namespace)
run=namespace['run']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','preflight','worker','run'))
    p.add_argument('--lead',type=int,choices=(2,4));p.add_argument('--seed',type=int,choices=range(11,16));p.add_argument('--offline',action='store_true')
    a=p.parse_args()
    if a.action=='worker':base.worker(a.lead,a.seed,a.offline)
    else:globals()[a.action]()
