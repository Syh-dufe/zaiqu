"""Same frozen deterministic ordering comparison on original trace3 rise/drop."""
import argparse,importlib.util,socket,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('drop_original_deterministic_runner',ROOT/'experiments/sundial_deterministic_cost/runner.py')
original=importlib.util.module_from_spec(spec);sys.modules[spec.name]=original;spec.loader.exec_module(original)
core=original.core;METHODS=original.METHODS
# In-memory scope adaptation only; every inherited source file remains frozen.
original.locked.SELECTED=(3,)
needle='env.n_eval=4;env.eval_index=2'
assert original.locked.evaluate_source.count(needle)==1
original.locked.evaluate_source=original.locked.evaluate_source.replace(needle,'env.n_eval=4;env.eval_index=3')
old_sources=core.source_hashes
def source_hashes():
 v=old_sources();files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/plans/2026-10-15-sundial-deterministic-drop.md']
 v.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return v
core.source_hashes=source_hashes
old_contracts=core.contracts
def contracts(*args,**kwargs):
 v=old_contracts(*args,**kwargs);v.update(selected_traces=[3],shock_type='surge_then_drop');return v
core.contracts=contracts
if __name__=='__main__':
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=(11,12,13,14,15),required=True);a,rest=p.parse_known_args()
 original.configure(a.seed);socket.socket=original.forbidden;sys.argv=[sys.argv[0]]+rest;core.main()
