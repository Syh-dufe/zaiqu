"""Seed and trace-count adapter around the frozen four/six-rule engines."""
import argparse,ast,importlib.util,inspect,os,socket,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
def module(name,path):
 if 'engine' in globals() and Path(path).resolve()==(ROOT/'experiments/deepseek_pilot/rules.py').resolve():return engine.module(name,path)
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
def setup(mode,seed):
 global core,guard,original,predictor,paths,METHODS,engine
 engine=module('extension_frozen_engine',ROOT/('experiments/sundial_response_live_api/runner.py' if mode=='merton' else 'experiments/sundial_six_rules/runner.py'))
 core,guard,original,predictor,paths=engine.core,engine.guard,engine.original,engine.predictor,engine.paths
 METHODS=('happo','original_merton') if mode=='merton' else ('adapted_sundial',);core.METHODS=METHODS
 core.training=lambda value:ROOT/f'results/learning_curve/curve_seed{value}_extension_v1'
 engine.configure(seed);factory=core.EventController
 def controller(group,*a,**kw):return original.EventController(group,*a,**kw) if group=='happo' else factory(group,*a,**kw)
 core.EventController=controller
 old_hashes=core.source_hashes
 def sources():
  v=old_hashes();v.update({str(p.relative_to(ROOT)):core.digest(p) for p in [*HERE.glob('*.py'),ROOT/'docs/superpowers/specs/2026-10-16-seeds16-20-fixed-comparison-design.md',ROOT/'docs/superpowers/plans/2026-10-16-seeds16-20-fixed-comparison.md']});return v
 core.source_hashes=sources
 text=inspect.getsource(core.validate_inputs)
 assert text.count('!=4')==3
 text=text.replace('!=4','!=3').replace('Exactly four registered traces','Exactly three registered traces')
 ns=dict(core.__dict__);exec(compile(text,str(HERE/'runner.py'),'exec'),ns);core.validate_inputs=ns['validate_inputs']
 tree=ast.parse((ROOT/'experiments/submission_required/run_online.py').read_text(encoding='utf-8'))
 node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='contracts')
 text=ast.get_source_segment((ROOT/'experiments/submission_required/run_online.py').read_text(encoding='utf-8'),node)
 needle="_,ippo_contract=load_policy('ippo',done['seed'])";assert text.count(needle)==1;text=text.replace(needle,'ippo_contract=None').replace('traces=4','traces=3')
 ns=dict(core.__dict__);exec(compile(text,str(HERE/'runner.py'),'exec'),ns);base_contract=ns['contracts']
 def contracts(*a,**kw):
  v=base_contract(*a,**kw);v.update(methods=list(METHODS),ippo_not_used=True,development_only=True,independent_confirmation=False,rule_limit=4 if mode=='merton' else 6,sundial_revision=predictor.REVISION,adapter_sha256=core.digest(predictor.ADAPTER),response_candidate='all_half',max_http_task=48,training_seed=seed)
  assert v['happo_contract']['seed']==seed;return v
 core.contracts=contracts
 text=guard.evaluate_source
 for before,after in [('range(4)','range(3)'),('env.n_eval=4','env.n_eval=3'),('len(METHODS)*8','len(METHODS)*6'),('len(METHODS)*4800','len(METHODS)*3600')]:
  assert before in text,before;text=text.replace(before,after)
 def evaluate(opts,out,contract,data):
  before=predictor.parameter_hash();ns=dict(core.__dict__);exec(compile(text,str(HERE/'runner.py'),'exec'),ns);ns['evaluate'](opts,out,contract,data)
  after=predictor.parameter_hash();assert before==after
  core.write(out/'forecast_model_checks.json',dict(before=before,after=after,unchanged=True,adapter_sha256=core.digest(predictor.ADAPTER),actually_used=(mode=='sundial')))
 core.evaluate=evaluate
 return contracts
def main():
 p=argparse.ArgumentParser();p.add_argument('--seed',type=int,choices=range(16,21),required=True);p.add_argument('--mode',choices=('merton','sundial'),required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reference',type=Path);p.add_argument('--offline',action='store_true');a=p.parse_args()
 setup(a.mode,a.seed);assert not a.out.exists();a.out.mkdir(parents=True)
 if a.offline:
  original_contracts=core.contracts
  def offline_contracts(*args,**kwargs):kwargs['require_key']=False;return original_contracts(*args,**kwargs)
  core.contracts=offline_contracts
  class Fake:
   def __init__(self,out,*args):self.records=[];self.episode_http=0;core.write(out/'calls.json',[])
   def reset_episode(self):self.episode_http=0
   def generate(self,context,count,identity,stage):
    rule={'rules':[{'when':'False','delta':'0'} for _ in range((4 if a.mode=='merton' else 6)-1)]+[{'when':'True','delta':'0'}]}
    return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=rule,compiled=core.compile_rule(rule)) for i in range(count)]
  core.Client=Fake
  def forbidden(*args,**kw):raise RuntimeError('Network prohibited in offline fixture')
  socket.socket.connect=forbidden;socket.create_connection=forbidden
 else:module('extension_secure_common',ROOT/'experiments/submission_required/common.py').key_from_user()
 try:
  contract=core.contracts(a.input,core.LIBRARY,core.training(a.seed),require_key=not a.offline);data=core.validate_inputs(core.read(a.input))
  core.write(a.out/'protocol.json',dict(contract,system=core.SYSTEM,offline_fixture=a.offline));core.write(a.out/'demands.json',data)
  opts=argparse.Namespace(input_file=a.input,operator_library=core.LIBRARY,training_directory=core.training(a.seed),phase='development')
  core.evaluate(opts,a.out,contract,data)
  auditor=module('extension_raw_auditor',HERE/'audit.py');auditor.audit(sys.modules[__name__],a.out,data,contract['expected_parameter_sha256'],a.reference,a.offline)
  print('SEED_EXTENSION_TASK_PASSED',a.seed,a.mode,flush=True)
 except Exception as e:core.write(a.out/'failed.json',dict(type=type(e).__name__,detail=str(e)[:1000],preserved=True));raise
if __name__=='__main__':main()
