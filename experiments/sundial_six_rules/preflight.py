"""Eight zero-rule no-network episodes on exact historical paired input."""
import argparse,socket
import runner
ROOT=runner.ROOT;OUT=ROOT/'results/sundial_six_rules/no_api_fixture_v1';INPUT=ROOT/'results/submission_required/v1/inputs/confirmation01_main.json'
def run():
 assert not OUT.exists();OUT.mkdir(parents=True);core=runner.core;runner.configure(11)
 class Fake:
  def __init__(self,out,*args):self.records=[];self.episode_http=0;core.write(out/'calls.json',[])
  def reset_episode(self):self.episode_http=0
  def generate(self,context,count,identity,stage):
   rule={'rules':[{'when':'False','delta':'0'} for _ in range(5)]+[{'when':'True','delta':'0'}]};return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=rule,compiled=core.compile_rule(rule)) for i in range(count)]
 core.Client=Fake;old=core.contracts
 def contracts(*a,**kw):kw['require_key']=False;return old(*a,**kw)
 core.contracts=contracts
 def forbidden(*a,**kw):raise RuntimeError('No network allowed')
 socket.socket=forbidden;contract=core.contracts(INPUT,core.LIBRARY,core.training(11));data=core.read(INPUT);core.write(OUT/'protocol.json',dict(contract,system=core.SYSTEM));core.write(OUT/'demands.json',data)
 opts=argparse.Namespace(input_file=INPUT,operator_library=core.LIBRARY,training_directory=core.training(11),phase='development')
 try:
  core.evaluate(opts,OUT,contract,data);auditor=runner.module('cached_explicit_auditor',runner.HERE/'audit.py');v=auditor.audit(runner,OUT,data,contract['expected_parameter_sha256'],True);core.write(OUT/'preflight_passed.json',dict(**v,network_requests=0,fake_zero_rules_not_performance=True));print('CACHED_MERTON_FIXTURE_PASSED',flush=True)
 except Exception as e:core.write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),api=0,preserved=True));raise
if __name__=='__main__':run()
