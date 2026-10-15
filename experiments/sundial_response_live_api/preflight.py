"""Full fake-zero DSL wiring including tail audit; physically no network."""
import argparse,socket,sys,urllib.request,json
from pathlib import Path
import runner
ROOT=runner.ROOT;OUT=ROOT/'results/sundial_response_live_api/no_api_fixture_v1'
INPUT=ROOT/'results/sundial_change_response/v1/reserved_validation_inputs.json'
def balance():
 common=runner.module('response_live_secure_common',ROOT/'experiments/submission_required/common.py');common.key_from_user()
 request=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+__import__('os').environ['DEEPSEEK_API_KEY']})
 with urllib.request.urlopen(request,timeout=30) as response:value=json.loads(response.read())
 print('API_BALANCE_AVAILABLE',value.get('is_available') is True,flush=True)
def fixture():
 assert not OUT.exists();OUT.mkdir(parents=True);core=runner.core;runner.configure(11)
 class Fake:
  def __init__(self,out,*args):self.records=[];self.episode_http=0;core.write(out/'calls.json',[])
  def reset_episode(self):self.episode_http=0
  def generate(self,context,count,identity,stage):
   rule={'rules':[{'when':'True','delta':'0'}]}
   return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=rule,compiled=core.compile_rule(rule)) for i in range(count)]
 core.Client=Fake;old=core.contracts
 def contracts(*args,**kwargs):kwargs['require_key']=False;return old(*args,**kwargs)
 core.contracts=contracts
 def forbidden(*args,**kwargs):raise RuntimeError('No network allowed in full fixture')
 socket.socket=forbidden
 contract=core.contracts(INPUT,core.LIBRARY,core.training(11));data=core.read(INPUT);core.write(OUT/'protocol.json',dict(contract,system=core.SYSTEM));core.write(OUT/'demands.json',data)
 opts=argparse.Namespace(input_file=INPUT,operator_library=core.LIBRARY,training_directory=core.training(11),phase='development')
 try:
  core.evaluate(opts,OUT,contract,data);auditor=runner.module('response_live_local_auditor',runner.HERE/'audit.py');result=auditor.audit(runner,OUT,data,contract['expected_parameter_sha256'],True)
  core.write(OUT/'preflight_passed.json',dict(**result,network_requests=0,fake_zero_rules_not_performance=True));print('RESPONSE_LIVE_FULL_FIXTURE_PASSED',flush=True)
 except Exception as e:core.write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),api=0,preserved=True));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('balance','fixture'));a=p.parse_args();{'balance':balance,'fixture':fixture}[a.action]()
