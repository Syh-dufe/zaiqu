"""All-four-profile no-LLM cost calibration with one frozen response candidate."""
import argparse,importlib.util,socket,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
original=module('response_original_deterministic',ROOT/'experiments/sundial_deterministic_cost/runner.py');predictor=module('change_response_predictor',HERE/'predictor.py')
core=original.core;METHODS=('adapted_sundial',);core.METHODS=METHODS;original.locked.predictor=predictor;original.locked.SELECTED=(0,1,2,3)
text=original.locked.evaluate_source
for before,after,count in [('env.n_eval=4;env.eval_index=2','env.n_eval=4;env.eval_index=0',1),('len(METHODS)*2','len(METHODS)*8',1),('len(METHODS)*1200','len(METHODS)*4800',2)]:
 assert text.count(before)==count,before;text=text.replace(before,after)
original.locked.evaluate_source=text
old_sources=core.source_hashes
def sources():
 v=old_sources();files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/specs/2026-10-15-sundial-change-response-design.md',ROOT/'docs/superpowers/plans/2026-10-15-sundial-change-response.md']
 v.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return v
core.source_hashes=sources;old_contracts=core.contracts
def contracts(*args,**kwargs):
 v=old_contracts(*args,**kwargs);v.update(methods=list(METHODS),selected_traces=[0,1,2,3],evaluated_trace_count=4,actual_variant='change_response_'+predictor.CANDIDATE,response_candidate=predictor.CANDIDATE);return v
core.contracts=contracts
old_evaluate=core.evaluate
def evaluate(*args,**kwargs):
 old_evaluate(*args,**kwargs);out=args[1];v=core.read(out/'forecast_model_checks.json');v.update(actual_variant='change_response_'+predictor.CANDIDATE);core.write(out/'forecast_model_checks.json',v)
core.evaluate=evaluate
if __name__=='__main__':
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=(11,14),required=True);p.add_argument('--candidate',choices=tuple(predictor.response.CANDIDATES),required=True);a,rest=p.parse_known_args()
 predictor.CANDIDATE=a.candidate;original.configure(a.seed);socket.socket=original.forbidden;sys.argv=[sys.argv[0]]+rest;core.main()
