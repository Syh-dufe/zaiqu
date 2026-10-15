"""Frozen HAPPO and existing deterministic_search, predictor-only comparison."""
import argparse,inspect,socket,sys,time,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('deterministic_locked_cost',ROOT/'experiments/sundial_multiscale_cost/runner.py')
locked=importlib.util.module_from_spec(spec);sys.modules[spec.name]=locked;spec.loader.exec_module(locked)
core=locked.core;module=locked.module
METHODS=('original_merton','native_sundial','adapted_sundial');core.METHODS=METHODS
component=sys.modules['component'];original=locked.original
source=inspect.getsource(component.ComponentController)
plan=ROOT/'docs/superpowers/plans/2026-10-15-sundial-deterministic-cost.md'
old_sources=core.source_hashes
def sources():
 v=old_sources();v.update({str(p.relative_to(ROOT)):core.digest(p) for p in list(HERE.glob('*.py'))+[plan]});return v
core.source_hashes=sources
old_contract=core.contracts
def contracts(*args,**kwargs):
 kwargs['require_key']=False;v=old_contract(*args,**kwargs)
 v.update(methods=list(METHODS),ordering_controller='existing_deterministic_search',api_budget=0,actual_variant='predictor_only_no_llm',independent_confirmation=False,development_only=True)
 return v
core.contracts=contracts
class NoClient:
 def __init__(self,out,*args):self.records=[];self.episode_http=0;core.write(out/'calls.json',[])
 def reset_episode(self):self.episode_http=0
 def generate(self,*args,**kwargs):raise AssertionError('LLM generation forbidden')
core.Client=NoClient
def configure(seed):
 def create(group,client,library,random_rules,identity):
  assert group in METHODS
  provider=locked.predictor.Centers() if group=='adapted_sundial' else locked.predictor.base.Centers();last={}
  def forecast(history,trace,period,method='merton',report_age=0):
   assert period==len(history)+report_age
   h=min(20,200-period);sid=f'b1_s{seed}_t{trace}_p{period+1}'
   common=dict(provider=group,decision_period=period+1,report_age=report_age,delivered_through=period-report_age,stream_identity=sid)
   if group=='original_merton':
    pair=original.forecasts(history,trace,period,'merton',report_age);last.clear();last.update(common);return pair
   value,audit=provider.forecast(history,report_age,h,sid,group=='adapted_sundial')
   last.clear();last.update(common,prediction=audit);paths=value['deployment'];return paths[:3],paths[3:]
  ns=dict(component.__dict__,forecasts=forecast);exec(compile(source,str(Path(component.__file__)),'exec'),ns)
  inner=ns['ComponentController']('deterministic_search',client,library,random_rules,identity);decide=inner.decide
  def decision(*args,**kwargs):
   action,record=decide(*args,**kwargs)
   if record and 'forecasts' in record:record.update(forecast_audit=dict(last),actual_group=group,no_llm=True)
   return action,record
  inner.decide=decision;return inner
 core.EventController=create
def forbidden(*args,**kwargs):raise AssertionError('Network forbidden in deterministic cost experiment')
if __name__=='__main__':
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=(14,15),required=True);a,rest=p.parse_known_args()
 configure(a.seed);socket.socket=forbidden;sys.argv=[sys.argv[0]]+rest;core.main()
