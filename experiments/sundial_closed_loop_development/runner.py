"""Independent runner: old author, actor, prompt, client and controller untouched."""
import argparse,sys,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(spec);sys.modules[name]=v;spec.loader.exec_module(v);return v
guard=module('sundial_guard_runner',ROOT/'experiments/online_llm_guard_pool/runner.py');core=guard.core;original=guard.original
adapter=module('sundial_injected_controller',HERE/'controller.py');predictor=module('sundial_frozen_predictor',HERE/'predictor.py')
paths=module('sundial_locked_naive_paths',ROOT/'experiments/timesfm_path_development/paths.py');METHODS=adapter.METHODS;core.METHODS=METHODS
old_sources=core.source_hashes
def source_hashes():
 values=old_sources();files=list(HERE.glob('*.py'))+[ROOT/'experiments/timesfm_path_development/paths.py',ROOT/'experiments/sundial_adapter_development/adapter.py',
 ROOT/'docs/superpowers/specs/2026-10-14-sundial-closed-loop-design.md',ROOT/'docs/superpowers/plans/2026-10-14-sundial-closed-loop.md']
 values.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return values
core.source_hashes=source_hashes;old_contract=core.contracts
def contracts(*args,**kwargs):
 value=old_contract(*args,**kwargs);value.update(development_only=True,independent_confirmation=False,forecast_upgrade='frozen_sundial_integer_block_allocation',
 methods=list(core.METHODS),sundial_revision=predictor.REVISION,adapter_sha256=core.digest(predictor.ADAPTER),
 prompt_forecast_protocol='Original prompt retained; actual forecast source and block allocation recorded in forecast_audit')
 return value
core.contracts=contracts
old_evaluate=core.evaluate
def evaluate(opts,out,contract,data):
 before=predictor.parameter_hash()
 old_evaluate(opts,out,contract,data)
 after=predictor.parameter_hash();assert before==after
 core.write(out/'forecast_model_checks.json',dict(before=before,after=after,unchanged=True,adapter_sha256=core.digest(predictor.ADAPTER)))
core.evaluate=evaluate
def configure(seed,batch):core.EventController=adapter.factory(original,guard.adapter,predictor,paths,seed,batch)
if __name__=='__main__':
 parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--seed',type=int,required=True);parser.add_argument('--batch',type=int,required=True)
 opts,rest=parser.parse_known_args();sys.argv=[sys.argv[0]]+rest;configure(opts.seed,opts.batch)
 core.main()
