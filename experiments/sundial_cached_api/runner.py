"""Only new response-Sundial runs; historical real-Merton outputs stay read-only."""
import argparse,importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
locked=module('cached_original_live_runner',ROOT/'experiments/sundial_response_live_api/runner.py')
core=locked.core;guard=locked.guard;original=locked.original;predictor=locked.predictor;paths=locked.paths
METHODS=('adapted_sundial',);core.METHODS=METHODS
old_sources=core.source_hashes
def sources():
 v=old_sources();files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/plans/2026-10-15-response-sundial-cached-merton.md']
 v.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return v
core.source_hashes=sources;old_contracts=core.contracts
def contracts(*args,**kwargs):
 v=old_contracts(*args,**kwargs);v.update(methods=list(METHODS),api_budget_total=128,historical_merton_reused=True);return v
core.contracts=contracts
def configure(seed):locked.configure(seed)
if __name__=='__main__':
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=(11,12),required=True);a,rest=p.parse_known_args();configure(a.seed);sys.argv=[sys.argv[0]]+rest;core.main()
