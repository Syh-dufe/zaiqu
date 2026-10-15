"""Decision-cost adapter, frozen deterministic controller, no network or policy updates."""
import argparse,hashlib,importlib.util,inspect,json,math,socket,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
old=module('cost_adapter_deterministic',ROOT/'experiments/sundial_deterministic_cost/runner.py')
response=module('cost_adapter_response',ROOT/'experiments/sundial_change_response/predictor.py')
core=old.core;PARAMETERS=[0.,0.,1.];PARAM_FILE=None;METHODS=('cost_sundial',)
CACHE=ROOT/'results/sundial_cost_adapter/v1/forecast_cache'
PLAN=ROOT/'docs/superpowers/plans/2026-10-15-sundial-cost-adapter.md'
SPEC=ROOT/'docs/superpowers/specs/2026-10-15-sundial-cost-adapter-design.md'

def transform(samples,history,age,parameters):
 x=np.asarray(samples,dtype=np.float64);b,v,a=parameters
 assert -2<=b<=2 and 0<=v<=1 and .5<=a<=1.5
 if parameters==[0.,0.,1.]:return x.copy()
 mu=x.mean(0);d=float(np.clip(history[-1]-history[-2],-4,4)) if len(history)>1 else 0.
 trend=v*d*np.exp(-(age+3*np.arange(x.shape[1]))/6)
 return np.clip(mu[None,:]+b+trend[None,:]+a*(x-mu[None,:]),0,20)

def persistent_samples(blocks,count,identity):
 key=hashlib.sha256(json.dumps([response.REVISION,blocks,count,identity],separators=(',',':')).encode()).hexdigest()
 path=CACHE/(key+'.npz');CACHE.mkdir(parents=True,exist_ok=True)
 if path.exists():
  with np.load(path,allow_pickle=False) as z:raw=z['raw'].copy();seeds=z['seeds'].tolist()
 else:
  raw,seeds=persistent_samples_original(blocks,count,identity)
  # One serial driver owns the cache; no concurrent writers.
  with path.open('xb') as f:np.savez_compressed(f,raw=raw,seeds=np.asarray(seeds,dtype=np.int64))
 assert raw.shape==(32,count) and np.isfinite(raw).all()
 return raw,seeds

def validate(data):
 assert len(data['base'])==len(data['shock'])==len(data['events'])==3
 kinds=('single_surge','sustained_surge','double_surge')
 for t,e in enumerate(data['events']):
  assert e['type']==kinds[t]
  base=data['base'][t];assert len(base)==201
  expected=base.copy()
  for part in e['intervals']:
   for j in range(part['start'],part['end']):expected[j]=min(20,math.ceil(part['factor']*base[j]))
  assert expected==data['shock'][t] and all(type(v) is int and 0<=v<=20 for v in base+expected)
 return data
core.validate_inputs=validate
old_sources=core.source_hashes
def sources():
 v=old_sources();v.update({str(p.relative_to(ROOT)):core.digest(p) for p in list(HERE.glob('*.py'))+[SPEC,PLAN]});return v
core.source_hashes=sources
old_contract=core.contracts
def contracts(*a,**kw):
 kw['require_key']=False;v=old_contract(*a,**kw)
 v.update(methods=list(METHODS),traces=3,evaluated_trace_count=3,api_budget=0,actual_variant='decision_cost_adapter',selected_traces=[0,1,2],
          cost_parameters=PARAMETERS,parameter_file_sha256=core.digest(PARAM_FILE))
 return v
core.contracts=contracts

def configure(seed):
 core.METHODS=METHODS
 # Persistent cache stores only raw forecasts determined by delivered reports, not inventory or actions.
 response.base.base.sample_blocks=persistent_samples_original
 def create(group,client,library,random_rules,identity):
  provider=response.Centers();last={}
  def forecast(history,trace,period,method='merton',report_age=0):
   assert period==len(history)+report_age
   horizon=min(20,200-period);sid=f'b1_s{seed}_t{trace}_p{period+1}'
   common=dict(provider=group,decision_period=period+1,report_age=report_age,delivered_through=period-report_age,stream_identity=sid,horizon=horizon)
   if group=='original_merton':
    value=old.original.forecasts(history,trace,period,'merton',report_age);last.clear();last.update(common);return value
   # Existing multiscale provider looks up sample_blocks on its base module.
   old_sampler=response.base.base.sample_blocks
   response.base.base.sample_blocks=persistent_samples
   try:value,audit=provider.forecast(history,report_age,horizon,sid,True)
   finally:response.base.base.sample_blocks=old_sampler
   before=np.asarray(audit['selected_blocks'],dtype=np.float64)
   parameters=PARAMETERS if group=='cost_sundial' else [0.,0.,1.]
   selected=transform(before,audit['block_history'],report_age,parameters)
   allocated=response.base.allocate(selected,report_age,horizon,sid)
   audit.update(cost_base_blocks=before.tolist(),cost_blocks=selected.tolist(),cost_parameters=parameters,
                cost_paths=allocated['paths'],cost_allocation_totals=allocated['totals'],cost_allocation_seeds=allocated['allocation_seeds'])
   last.clear();last.update(common,prediction=audit)
   return allocated['deployment'][:3],allocated['deployment'][3:]
  ns=dict(old.component.__dict__,forecasts=forecast);exec(compile(old.source,str(Path(old.component.__file__)),'exec'),ns)
  inner=ns['ComponentController']('deterministic_search',client,library,random_rules,identity);decide=inner.decide
  def decision(*a,**kw):
   action,record=decide(*a,**kw)
   if record and 'forecasts' in record:record.update(forecast_audit=dict(last),actual_group=group,no_llm=True)
   return action,record
  inner.decide=decision;return inner
 core.EventController=create

persistent_samples_original=response.base.base.sample_blocks
response.CANDIDATE='all_half'
text=old.locked.evaluate_source
for before,after,n in [('env.n_eval=4;env.eval_index=2','env.n_eval=3;env.eval_index=0',1),('len(METHODS)*2','len(METHODS)*6',1),('len(METHODS)*1200','len(METHODS)*3600',2)]:
 assert text.count(before)==n,before;text=text.replace(before,after)
def evaluate(opts,out,contract,data):
 before=response.parameter_hash();ns=dict(core.__dict__,SELECTED=(0,1,2));exec(compile(text,str(HERE/'runner.py'),'exec'),ns);ns['evaluate'](opts,out,contract,data)
 after=response.parameter_hash();assert before==after
 core.write(out/'forecast_model_checks.json',dict(before=before,after=after,unchanged=True,adapter_sha256=core.digest(response.ADAPTER)))
core.evaluate=evaluate

if __name__=='__main__':
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=range(11,16),required=True);p.add_argument('--parameters',type=Path,required=True);p.add_argument('--methods',default='cost_sundial')
 a,rest=p.parse_known_args();PARAM_FILE=a.parameters.resolve();PARAMETERS=core.read(PARAM_FILE)['parameters'];METHODS=tuple(a.methods.split(','))
 assert set(METHODS)<= {'cost_sundial','old_sundial','original_merton'}
 transform(np.ones((32,2)),[10.,11.],0,PARAMETERS);configure(a.seed);socket.socket=old.forbidden
 sys.argv=[sys.argv[0]]+rest;core.main()
