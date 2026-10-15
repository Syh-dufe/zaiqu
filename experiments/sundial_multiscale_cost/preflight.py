"""Two whole episodes with fixed historical replies, network physically blocked."""
import argparse,copy,socket
import runner
core=runner.core;ROOT=runner.ROOT;OUT=ROOT/'results/sundial_multiscale_cost/no_api_fixture_v2'
def run():
 assert not OUT.exists();OUT.mkdir(parents=True);runner.configure(14)
 source=ROOT/'results/sundial_focus_completion/v1/runs/seed14_two_types'
 records=[r for r in core.read(source/'calls.json') if r['group']=='adapted_sundial' and r['trace']==2]
 class Replay:
  def __init__(self,output,*args):self.records=[];self.episode_http=0;self.output=output;core.write(output/'calls.json',[])
  def reset_episode(self):self.episode_http=0
  def generate(self,context,count,identity,stage):
   matched=[r for r in records if r['stage']==stage and all(r[k]==identity[k] for k in ('group','scenario','trace','decision_period','event'))];assert matched
   self.records.extend(dict(copy.deepcopy(r),network_requests=0,replayed=True) for r in matched);self.episode_http+=len(matched);core.write(self.output/'calls.json',self.records)
   valid=[r for r in matched if r['status']=='valid']
   if not valid:return []
   values=valid[-1]['candidates'];assert len(values)==count
   return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=v,compiled=core.compile_rule(v)) for i,v in enumerate(values)]
 core.Client=Replay;old=core.contracts
 def contracts(*args,**kwargs):kwargs['require_key']=False;return old(*args,**kwargs)
 core.contracts=contracts
 def forbidden(*args,**kwargs):raise RuntimeError('No network allowed in full fixture')
 socket.socket=forbidden
 inp=ROOT/'results/sundial_closed_loop_development/development_v2/inputs/stationary.json';contract=core.contracts(inp,core.LIBRARY,core.training(14));data=core.read(inp)
 core.write(OUT/'protocol.json',dict(contract,system=core.SYSTEM));core.write(OUT/'demands.json',data)
 opts=argparse.Namespace(input_file=inp,operator_library=core.LIBRARY,training_directory=core.training(14),phase='development')
 try:
  core.evaluate(opts,OUT,contract,data);auditor=runner.module('multiscale_fixture_auditor',runner.HERE/'audit.py');result=auditor.audit(runner,OUT,data,contract['expected_parameter_sha256'],True)
  core.write(OUT/'preflight_passed.json',dict(**result,network_requests=0,fixed_old_replies_not_live_performance=True))
  print('MULTISCALE_DOUBLE_FIXTURE_PASSED',flush=True)
 except Exception as error:core.write(OUT/'failed.json',dict(error=type(error).__name__,detail=str(error),api=0,preserved=True));raise
if __name__=='__main__':run()
