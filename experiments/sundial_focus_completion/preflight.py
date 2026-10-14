"""Offline response replay proves subset runner preserves original behavior."""
import argparse,copy,csv,socket
from pathlib import Path
import runner
core=runner.core;ROOT=runner.ROOT;OUT=ROOT/'results/sundial_focus_completion/no_api_replay_v1'
SOURCE=ROOT/'results/sundial_closed_loop_development/development_v2/runs/batch01_seed11'

def run():
 assert not OUT.exists(),'Preserve prior fixture'
 inp=ROOT/'results/sundial_closed_loop_development/development_v2/inputs/stationary.json';runner.configure(11)
 saved=core.contracts
 def contracts(*a,**kw):kw['require_key']=False;return saved(*a,**kw)
 core.contracts=contracts;contract=core.contracts(inp,core.LIBRARY,core.training(11));data=core.read(inp)
 records=core.read(SOURCE/'calls.json');selected=[r for r in records if r['group'] in runner.METHODS and r['trace'] in runner.SELECTED]
 OUT.mkdir(parents=True);core.write(OUT/'protocol.json',dict(contract,system=core.SYSTEM));core.write(OUT/'demands.json',data)
 assert core.SYSTEM==core.read(SOURCE/'protocol.json')['system']
 class ReplayClient:
  def __init__(self,output,system,model):self.output=output;self.records=[];self.episode_http=0;self.used=set();core.write(output/'calls.json',[])
  def reset_episode(self):self.episode_http=0
  def generate(self,context,count,identity,stage):
   group=[(i,r) for i,r in enumerate(selected) if r['stage']==stage and all(r[k]==identity[k] for k in ('group','scenario','trace','decision_period','event'))]
   assert group and not any(i in self.used for i,_ in group)
   for i,r in group:self.used.add(i);record=copy.deepcopy(r);record.update(network_requests=0,replayed=True);self.records.append(record)
   self.episode_http+=len(group);assert self.episode_http<=16;core.write(self.output/'calls.json',self.records)
   valid=[r for _,r in group if r['status']=='valid']
   if not valid:return []
   values=valid[-1]['candidates'];assert len(values)==count
   return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=v,compiled=core.compile_rule(v)) for i,v in enumerate(values)]
 core.Client=ReplayClient
 def forbidden(*a,**kw):raise RuntimeError('Networking forbidden in replay fixture')
 socket.socket=forbidden
 opts=argparse.Namespace(input_file=inp,operator_library=core.LIBRARY,training_directory=core.training(11),phase='development')
 try:
  core.evaluate(opts,OUT,contract,data)
  audit=runner.module('focus_replay_audit',runner.HERE/'audit.py');result=audit.audit(runner,OUT,data,contract['expected_parameter_sha256'],True)
  with (SOURCE/'periods.csv').open(encoding='utf-8',newline='') as f:reference={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in csv.DictReader(f)}
  with (OUT/'periods.csv').open(encoding='utf-8',newline='') as f:
   for r in csv.DictReader(f):
    key=(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node']));old=reference[key]
    assert all(r[k]==old[k] for k in ('demand','actual_order','policy_order','inventory','backlog','cost','chosen'))
  old_scores={(r['group'],r['trace'],r['decision_period']):r for r in core.read(SOURCE/'scores.json')}
  for r in core.read(OUT/'scores.json'):
   old=old_scores[r['group'],r['trace'],r['decision_period']];assert r['forecasts']==old['forecasts'] and r['chosen']==old['chosen']
  assert len(core.read(OUT/'calls.json'))==len(selected)
  core.write(OUT/'preflight_passed.json',dict(**result,network_requests=0,old_response_replay=True,exact_old_node_periods=True,exact_old_forecast_choices=True,not_new_performance_evidence=True))
  print('FOCUS_SUBSET_EXACT_REPLAY_PASSED',flush=True)
 except Exception as e:core.write(OUT/'failed.json',dict(error=type(e).__name__,detail=str(e),api=0,preserved=True));raise
if __name__=='__main__':run()
