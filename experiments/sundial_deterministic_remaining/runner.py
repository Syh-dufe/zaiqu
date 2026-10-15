"""Unchanged deterministic ordering on original single/sustained surge traces."""
import argparse,importlib.util,socket,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('remaining_original_deterministic',ROOT/'experiments/sundial_deterministic_cost/runner.py')
original=importlib.util.module_from_spec(spec);sys.modules[spec.name]=original;spec.loader.exec_module(original)
core=original.core;METHODS=original.METHODS;TRACE=0
evaluation_template=original.locked.evaluate_source
def select_trace(trace):
 global TRACE
 assert trace in (0,1);TRACE=trace;original.locked.SELECTED=(trace,)
 needle='env.n_eval=4;env.eval_index=2';assert evaluation_template.count(needle)==1
 original.locked.evaluate_source=evaluation_template.replace(needle,f'env.n_eval=4;env.eval_index={trace}')
old_sources=core.source_hashes
def source_hashes():
 v=old_sources();files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/plans/2026-10-15-sundial-deterministic-remaining.md']
 v.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return v
core.source_hashes=source_hashes
old_contracts=core.contracts
def contracts(*args,**kwargs):
 v=old_contracts(*args,**kwargs);v.update(selected_traces=[TRACE],shock_type=('single_surge','sustained_surge')[TRACE]);return v
core.contracts=contracts
if __name__=='__main__':
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=(11,12,13,14,15),required=True);p.add_argument('--trace',type=int,choices=(0,1),required=True);a,rest=p.parse_known_args()
 select_trace(a.trace);original.configure(a.seed);socket.socket=original.forbidden;sys.argv=[sys.argv[0]]+rest;core.main()
