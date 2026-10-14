"""Subset loop with original trace IDs and identical deployable controller."""
import argparse,sys,inspect,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
locked=module('focus_locked_sundial_runner',ROOT/'experiments/sundial_closed_loop_development/runner.py')
core=locked.core;original=locked.original;guard=locked.guard;predictor=locked.predictor;paths=locked.paths
METHODS=('original_merton','adapted_sundial');SELECTED=(2,3);core.METHODS=METHODS
old_sources=core.source_hashes
def source_hashes():
 v=old_sources();files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/specs/2026-10-15-sundial-focus-completion-design.md',ROOT/'docs/superpowers/plans/2026-10-15-sundial-focus-completion.md']
 v.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return v
core.source_hashes=source_hashes;old_contract=core.contracts
def contracts(*a,**kw):
 v=old_contract(*a,**kw);v.update(selected_traces=list(SELECTED),evaluated_trace_count=2,post_selected_development=True,methods=list(METHODS));return v
core.contracts=contracts
evaluate_source=locked.guard.evaluate_source
def replace(before,after,count):
 global evaluate_source
 assert evaluate_source.count(before)==count,before;evaluate_source=evaluate_source.replace(before,after)
replace('    class Controller(DummyVecEnv):','    class Controller(DummyVecEnv):\n        def get_eval_num(self):return len(SELECTED)',1)
replace('env.n_eval=4;env.eval_index=0','env.n_eval=4;env.eval_index=2',1)
replace('len(METHODS)*8','len(METHODS)*4',1)
replace('len(METHODS)*4800','len(METHODS)*2400',2)
replace('for trace in range(4):','for trace in SELECTED:',2)
replace("    for trace,event in enumerate(data['events']):","    for trace in SELECTED:\n        event=data['events'][trace]",1)
def evaluate(opts,out,contract,data):
 before=predictor.parameter_hash();namespace=dict(core.__dict__,SELECTED=SELECTED)
 exec(compile(evaluate_source,str(Path(__file__)),'exec'),namespace);namespace['evaluate'](opts,out,contract,data)
 after=predictor.parameter_hash();assert before==after
 core.write(out/'forecast_model_checks.json',dict(before=before,after=after,unchanged=True,adapter_sha256=core.digest(predictor.ADAPTER)))
core.evaluate=evaluate
def configure(seed):locked.configure(seed,1)
if __name__=='__main__':
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,required=True);a,rest=p.parse_known_args();sys.argv=[sys.argv[0]]+rest;configure(a.seed);core.main()
