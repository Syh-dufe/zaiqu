"""Independent four-forecast deployment. Original author/client sources untouched."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
import importlib.util
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(spec)
    sys.modules[name]=v;spec.loader.exec_module(v);return v
guard=module('timesfm_guard_runner',ROOT/'experiments/online_llm_guard_pool/runner.py')
core=guard.core;original=guard.original
adapter=module('timesfm_injected_controller',HERE/'controller.py')
predictor=module('timesfm_center_predictor',HERE/'predictor.py')
paths=module('timesfm_locked_paths',ROOT/'experiments/timesfm_path_development/paths.py')
METHODS=adapter.METHODS;core.METHODS=METHODS
old_sources=core.source_hashes
def source_hashes():
    values=old_sources()
    files=list(HERE.glob('*.py'))+[ROOT/'experiments/timesfm_path_development/paths.py',
        ROOT/'docs/superpowers/specs/2026-10-14-timesfm-closed-loop-design.md',ROOT/'docs/superpowers/plans/2026-10-14-timesfm-closed-loop.md']
    values.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return values
core.source_hashes=source_hashes
old_contract=core.contracts
def contracts(*args,**kwargs):
    value=old_contract(*args,**kwargs)
    value.update(development_only=True,independent_confirmation=False,forecast_upgrade='frozen_timesfm_joint_path_adapter',
        methods=list(core.METHODS),timesfm_revision=predictor.REVISION,prompt_forecast_protocol='Historical prompt retained verbatim; actual forecast source disclosed in forecast_audit')
    return value
core.contracts=contracts

def configure(seed,batch):core.EventController=adapter.factory(original,guard.adapter,predictor,paths,seed,batch)

if __name__=='__main__':
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--seed',type=int,required=True);parser.add_argument('--batch',type=int,required=True)
    opts,rest=parser.parse_known_args();sys.argv=[sys.argv[0]]+rest
    configure(opts.seed,opts.batch);core.main()
