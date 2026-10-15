"""Original real guard-pool LLM, Merton versus selected response-Sundial."""
import argparse,importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
locked=module('response_live_original_sundial',ROOT/'experiments/sundial_closed_loop_development/runner.py')
core=locked.core;guard=locked.guard;original=locked.original;paths=locked.paths
predictor=module('response_live_selected_predictor',ROOT/'experiments/sundial_change_response/predictor.py');predictor.CANDIDATE='all_half'
predictor.stream_seed=predictor.base.stream_seed;predictor.correction=predictor.base.correction
METHODS=('original_merton','adapted_sundial');core.METHODS=METHODS
old_sources=core.source_hashes
def sources():
 v=old_sources();files=list(HERE.glob('*.py'))+list((ROOT/'experiments/sundial_change_response').glob('*.py'))+[ROOT/'experiments/sundial_multiscale_cost/predictor.py',ROOT/'docs/superpowers/specs/2026-10-15-sundial-response-live-api-design.md',ROOT/'docs/superpowers/plans/2026-10-15-sundial-response-live-api.md']
 v.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return v
core.source_hashes=sources;old_contracts=core.contracts
def contracts(*args,**kwargs):
 v=old_contracts(*args,**kwargs);v.update(methods=list(METHODS),adapter_sha256=core.digest(predictor.ADAPTER),actual_variant='response_all_half_real_guard_pool',response_candidate='all_half',api_budget_total=256,development_only=True,independent_confirmation=False);return v
core.contracts=contracts
OriginalClient=core.Client
class StrictClient(OriginalClient):
 def generate(self,*args,**kwargs):
  result=super().generate(*args,**kwargs)
  if not result:raise RuntimeError('No valid API candidates; stop and preserve partial call records')
  return result
core.Client=StrictClient
def configure(seed):core.EventController=locked.adapter.factory(original,guard.adapter,predictor,paths,seed,1)
def evaluate(*args,**kwargs):
 before=predictor.parameter_hash();guard.evaluate(*args,**kwargs);after=predictor.parameter_hash();assert before==after
 core.write(args[1]/'forecast_model_checks.json',dict(before=before,after=after,unchanged=True,adapter_sha256=core.digest(predictor.ADAPTER),actual_variant='response_all_half_real_guard_pool'))
core.evaluate=evaluate
if __name__=='__main__':
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=(11,14),required=True);a,rest=p.parse_known_args();configure(a.seed);sys.argv=[sys.argv[0]]+rest;core.main()
