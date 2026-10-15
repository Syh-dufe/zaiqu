"""Fixed historical LLM replies: controlled no-network development, not live API."""
import argparse,copy,csv,hashlib,importlib.util,json,socket,sys
from pathlib import Path
HERE=Path(__file__).parent;ROOT=HERE.parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
runner=load('representative_subset_frozen_runner',ROOT/'experiments/sundial_focus_completion/runner.py')
selection=load('representative_replay_selection',HERE/'selection.py')
core=runner.core
OUT=ROOT/'results/sundial_representative_paths/no_api_replay_v1'
def source(seed):
 return ROOT/(f'results/sundial_closed_loop_development/development_v2/runs/batch01_seed{seed}' if seed<13 else f'results/sundial_focus_completion/v1/runs/seed{seed}_two_types')
def run(seed):
 target=OUT/f'seed{seed}';assert not target.exists();target.mkdir(parents=True)
 old=source(seed);saved=core.read(old/'scores.json');calls=core.read(old/'calls.json');data=core.read(old/'demands.json')
 lookup={(r['trace'],r['decision_period']):r for r in saved if r['group']=='adapted_sundial'}
 bindings={str(p):core.digest(p) for p in old.rglob('*') if p.is_file()}
 frozen=core.source_hashes();own={str(p):core.digest(p) for p in HERE.glob('*.py')}
 core.write(target/'registration.json',dict(source_sha256=frozen,implementation_sha256=own,reused_sha256=bindings,api_budget=0,old_llm_replies_fixed=True,not_live_api_confirmation=True))
 class Replay:
  def __init__(self,*args):self.episode_http=0;self.records=[]
  def reset_episode(self):self.episode_http=0
  def generate(self,context,count,identity,stage):
   matching=[r for r in calls if r['stage']==stage and all(r[k]==identity[k] for k in ('group','scenario','trace','decision_period','event'))]
   assert matching
   for record in matching:self.records.append(dict(copy.deepcopy(record),network_requests=0,replayed=True,context_may_differ=True))
   self.episode_http+=len(matching);core.write(target/'calls.json',self.records)
   valid=[r for r in matching if r['status']=='valid']
   if not valid:return []
   values=valid[-1]['candidates'];assert len(values)==count
   return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=v,compiled=core.compile_rule(v)) for i,v in enumerate(values)]
 class CachedCenters:
  def forecast(self,history,age,horizon,identity,adapted):
   assert adapted
   trace=int(identity.split('_t')[1].split('_')[0]);period=int(identity.rsplit('_p',1)[1])
   v=copy.deepcopy(lookup[trace,period]['forecast_audit']['prediction'])
   blocks=[history[i] for i in range(0,len(history),3)]
   assert blocks==v['block_history'] and horizon==len(v['diagnostic_paths'][0])
   deployed,check=selection.select(v['diagnostic_paths']);v.update(path_selection=check,previous_indices=[0,1,2,16,17,18],cached_samples=True)
   return dict(paths=v['diagnostic_paths'],deployment=deployed),v
 provider=type('CachedProvider',(),dict(Centers=CachedCenters))
 core.Client=Replay;core.METHODS=('adapted_sundial',)
 core.EventController=runner.locked.adapter.factory(runner.original,runner.guard.adapter,provider,runner.paths,seed,1)
 original_contract=core.contracts
 def contracts(*args,**kwargs):kwargs['require_key']=False;return original_contract(*args,**kwargs)
 core.contracts=contracts
 def forbidden(*args,**kwargs):raise RuntimeError('Network forbidden in fixed-response replay')
 socket.socket=forbidden
 inp=ROOT/'results/sundial_closed_loop_development/development_v2/inputs/stationary.json'
 contract=core.contracts(inp,core.LIBRARY,core.training(seed))
 opts=argparse.Namespace(input_file=inp,operator_library=core.LIBRARY,training_directory=core.training(seed),phase='development')
 namespace=dict(core.__dict__,SELECTED=(2,3));exec(compile(runner.evaluate_source,str(Path(__file__)),'exec'),namespace)
 try:
  namespace['evaluate'](opts,target,contract,data)
  def rows(path):
   with path.open(encoding='utf-8',newline='') as stream:return list(csv.DictReader(stream))
  reference={(r['scenario'],r['trace'],r['period'],r['node']):r for r in rows(old/'periods.csv') if r['group']=='adapted_sundial'}
  current=rows(target/'periods.csv');assert len(current)==2400
  assert len({(r['scenario'],r['trace'],r['period'],r['node']) for r in current})==2400
  for r in current:
   assert float(r['cost'])==int(r['inventory'])+int(r['backlog'])
   if r['scenario']=='base' or int(r['period'])<data['events'][int(r['trace'])]['start_index']+3:
    oldrow=reference[r['scenario'],r['trace'],r['period'],r['node']]
    assert all(oldrow[k]==r[k] for k in ('demand','policy_order','actual_order','inventory','backlog','cost'))
  records=core.read(target/'calls.json');assert all(r['network_requests']==0 for r in records)
  assert frozen==core.source_hashes()
  for p,sha in dict(bindings,**own).items():assert core.digest(Path(p))==sha
  core.write(target/'replay_verification.json',dict(status='passed',network_requests=0,node_periods=2400,normal_and_pre_notice_equal=True,old_llm_replies_fixed=True,not_live_api_confirmation=True))
  print('REPRESENTATIVE_FIXED_RESPONSE_REPLAY_PASSED',seed,flush=True)
 except Exception as error:
  core.write(target/'failed.json',dict(error=type(error).__name__,detail=str(error),network_requests=0,preserved=True));raise
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int,choices=range(11,16),required=True);args=parser.parse_args();run(args.seed)
