"""One immutable balanced-adapted variant on all four existing traces."""
import argparse,importlib.util,socket,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
original=module('balanced_original_deterministic',ROOT/'experiments/sundial_deterministic_cost/runner.py')
predictor=module('balanced_predictor',HERE/'predictor.py');original.locked.predictor=predictor
core=original.core;METHODS=('adapted_sundial',);core.METHODS=METHODS;TRACE=0
template=original.locked.evaluate_source
def select_trace(trace):
 global TRACE
 assert trace in range(4);TRACE=trace;original.locked.SELECTED=(trace,)
 needle='env.n_eval=4;env.eval_index=2';assert template.count(needle)==1
 original.locked.evaluate_source=template.replace(needle,f'env.n_eval=4;env.eval_index={trace}')
old_sources=core.source_hashes
def source_hashes():
 v=old_sources();files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/specs/2026-10-15-sundial-allocation-design.md',ROOT/'docs/superpowers/plans/2026-10-15-sundial-allocation.md']
 v.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return v
core.source_hashes=source_hashes;old_contracts=core.contracts
def contracts(*args,**kwargs):
 v=old_contracts(*args,**kwargs);v.update(methods=list(METHODS),selected_traces=[TRACE],actual_variant='multiscale24_balanced',allocation_variant='balanced_rotating_remainder');return v
core.contracts=contracts
old_evaluate=core.evaluate
def evaluate(*args,**kwargs):
 old_evaluate(*args,**kwargs);out=args[1];v=core.read(out/'forecast_model_checks.json');v.update(actual_variant='multiscale24_balanced',allocation_variant='balanced_rotating_remainder');core.write(out/'forecast_model_checks.json',v)
core.evaluate=evaluate
if __name__=='__main__':
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=(11,12,13,14,15),required=True);p.add_argument('--trace',type=int,choices=(0,1,2,3),required=True);a,rest=p.parse_known_args()
 select_trace(a.trace);original.configure(a.seed);socket.socket=original.forbidden;sys.argv=[sys.argv[0]]+rest;core.main()
