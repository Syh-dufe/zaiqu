"""One physical double-surge path; original trace and forecast identities preserved."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
import importlib.util
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
locked=module('multiscale_cost_frozen_focus',ROOT/'experiments/sundial_focus_completion/runner.py')
core=locked.core;original=locked.original;guard=locked.guard;paths=locked.paths
predictor=module('multiscale_cost_predictor',HERE/'predictor.py')
METHODS=('adapted_sundial',);SELECTED=(2,);core.METHODS=METHODS
sources=core.source_hashes
def source_hashes():
 v=sources();v.update({str(p.relative_to(ROOT)):core.digest(p) for p in list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/plans/2026-10-15-multiscale-double-cost-development.md']});return v
core.source_hashes=source_hashes;old_contract=core.contracts
def contracts(*args,**kwargs):
 v=old_contract(*args,**kwargs);v.update(methods=list(METHODS),selected_traces=[2],evaluated_trace_count=1,actual_variant='multiscale24',adapter_sha256=core.digest(predictor.ADAPTER));return v
core.contracts=contracts
evaluate_source=locked.evaluate_source
needle='def get_eval_num(self):return len(SELECTED)';assert evaluate_source.count(needle)==1
evaluate_source=evaluate_source.replace(needle,needle+'\n        def get_eval_bw_res(self):return [float(np.mean(v)) for v in self.env_list[0].record_act_sta]')
for before,after,count in [('len(METHODS)*4','len(METHODS)*2',1),('len(METHODS)*2400','len(METHODS)*1200',2)]:
 assert evaluate_source.count(before)==count;evaluate_source=evaluate_source.replace(before,after)
def evaluate(opts,out,contract,data):
 before=predictor.parameter_hash();namespace=dict(core.__dict__,SELECTED=SELECTED)
 exec(compile(evaluate_source,str(Path(__file__)),'exec'),namespace);namespace['evaluate'](opts,out,contract,data)
 after=predictor.parameter_hash();assert before==after
 core.write(out/'forecast_model_checks.json',dict(before=before,after=after,unchanged=True,adapter_sha256=core.digest(predictor.ADAPTER),actual_variant='multiscale24'))
core.evaluate=evaluate
def configure(seed):core.EventController=locked.locked.adapter.factory(original,guard.adapter,predictor,paths,seed,1)
if __name__=='__main__':
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=(14,15),required=True);a,rest=p.parse_known_args();configure(a.seed);sys.argv=[sys.argv[0]]+rest;core.main()
