"""Offline matched-state diagnosis; future paths are retrospective labels only."""
import argparse,copy,csv,hashlib,importlib.util,json,socket,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
runner=load('double_diagnosis_frozen_runner',ROOT/'experiments/sundial_focus_completion/runner.py')
core=runner.core
OUT=ROOT/'results/sundial_double_diagnosis/v1'
read=core.read;write=core.write

def run(seed):
 source=ROOT/f'results/sundial_focus_completion/v1/runs/seed{seed}_two_types'
 target=OUT/f'seed{seed}';assert not target.exists();target.mkdir(parents=True)
 files={str(p):core.digest(p) for p in source.rglob('*') if p.is_file()}
 records=read(source/'calls.json');saved=read(source/'scores.json');data=read(source/'demands.json')
 index={(r['group'],r['trace'],r['decision_period']):r for r in saved}
 frozen=core.source_hashes();probes=[];points=(108,128) if seed==14 else (73,78)
 class Replay:
  def __init__(self,*args):self.episode_http=0;self.records=[]
  def reset_episode(self):self.episode_http=0
  def generate(self,context,count,identity,stage):
   matching=[r for r in records if r['stage']==stage and all(r[k]==identity[k] for k in ('group','scenario','trace','decision_period','event'))]
   assert matching;self.episode_http+=len(matching);self.records.extend(copy.deepcopy(matching));valid=[r for r in matching if r['status']=='valid']
   if not valid:return []
   assert len(valid[-1]['candidates'])==count
   return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=v,compiled=core.compile_rule(v)) for i,v in enumerate(valid[-1]['candidates'])]
 def pool(method,period):
  events=[r for r in saved if r['group']==method and r['trace']==2 and r.get('generation_event') and r['decision_period']<=period]
  return max(events,key=lambda r:r['decision_period'])['candidates']
 def create(group,client,library,random_rules,identity):
  isolated=types.SimpleNamespace(**runner.original.__dict__)
  def forecasts(history,trace,period,method='merton',report_age=0):return copy.deepcopy(index[group,trace,period+1]['forecasts'])
  isolated.forecasts=forecasts
  controller=runner.guard.adapter.build_controller(isolated)('guard_pool',client,library,random_rules,identity)
  decide=controller.decide
  def wrapped(env,history,orders,proposed,recurrent,actors,reports,notify):
   actual,record=decide(env,history,orders,proposed,recurrent,actors,reports,notify)
   period=env.step_num+1
   if identity['scenario']=='shock' and identity['trace']==2 and period in points:
    candidates=[dict(id='zero')]
    for origin in runner.METHODS:
     candidates += [dict(id=origin+'::'+c['id'],rule=c['rule'],compiled=core.compile_rule(c['rule'])) for c in pool(origin,period) if c['id']!='zero']
    result=dict(state_owner=group,decision_period=period,selected=controller.chosen,labels_never_used_by_controller=True,candidates=[])
    state=runner.original.snapshot(env,history);visible=reports.delivered_history.copy()
    for c in candidates:
     values={}
     for provider in runner.METHODS:
      pair=index[provider,2,period]['forecasts']
      values[provider]=[runner.original.score(c,state,visible,orders,proposed,recurrent,actors,paths,5,reports.projection()) for paths in pair]
     future=data['shock'][2][period-1:min(200,period-1+20)]
     values['retrospective_true_future']=runner.original.score(c,state,visible,orders,proposed,recurrent,actors,[future],5,reports.projection())
     result['candidates'].append(dict(id=c['id'],rule=c.get('rule'),scores=values))
    probes.append(result);write(target/'matched_state_probes.json',probes)
   return actual,record
  controller.decide=wrapped;return controller
 core.Client=Replay;core.EventController=create
 def forbidden(*args,**kwargs):raise RuntimeError('Network forbidden during retrospective diagnosis')
 socket.socket=forbidden
 inp=ROOT/'results/sundial_closed_loop_development/development_v2/inputs/stationary.json'
 original_contract=core.contracts
 def contract(*args,**kwargs):kwargs['require_key']=False;return original_contract(*args,**kwargs)
 core.contracts=contract;c=core.contracts(inp,core.LIBRARY,core.training(seed))
 opts=argparse.Namespace(input_file=inp,operator_library=core.LIBRARY,training_directory=core.training(seed),phase='development')
 ns=dict(core.__dict__,SELECTED=runner.SELECTED);exec(compile(runner.evaluate_source,str(Path(__file__)),'exec'),ns)
 ns['evaluate'](opts,target,c,data)
 def rows(path):
  with path.open(encoding='utf-8',newline='') as stream:return {(r['group'],r['scenario'],r['trace'],r['period'],r['node']):r for r in csv.DictReader(stream)}
 old=rows(source/'periods.csv');new=rows(target/'periods.csv');assert old.keys()==new.keys()
 for identity,r in new.items():assert all(r[k]==old[identity][k] for k in ('policy_order','actual_order','inventory','backlog','cost','chosen','demand')),identity
 assert core.source_hashes()==frozen
 for p,sha in files.items():assert core.digest(Path(p))==sha
 write(target/'verification.json',dict(status='passed',network_requests=0,exact_original_node_periods=4800,matched_state_probes=len(probes),future_labels_only=True,source_sha256=frozen,reused_file_sha256=files))
 print('MATCHED_STATE_DIAGNOSIS_PASSED',seed,len(probes),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seed',type=int,required=True,choices=(14,15));a=p.parse_args();run(a.seed)
