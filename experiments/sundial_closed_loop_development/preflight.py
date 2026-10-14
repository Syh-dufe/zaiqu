"""Full real-policy fixture; no networking, not LLM performance evidence."""
import argparse,socket
import runner
core=runner.core;ROOT=runner.ROOT;OUT=ROOT/'results/sundial_closed_loop_development/no_api_fixture_v1'

def run():
 assert not OUT.exists(),'Preserve fixture attempt'
 manifest=core.read(ROOT/'results/sundial_closed_loop_development/development_v2/manifest.json');inp=__import__('pathlib').Path(manifest['inputs']['1']['path'])
 runner.configure(11,1);saved=core.contracts
 def contracts(*a,**kw):kw['require_key']=False;return saved(*a,**kw)
 core.contracts=contracts;contract=core.contracts(inp,core.LIBRARY,core.training(11));data=core.read(inp)
 assert core.SYSTEM==core.read(ROOT/'results/online_llm_guard_pool/development_v1/runs/development_batch01_seed11/protocol.json')['system']
 assert core.Client is __import__('client').Client
 OUT.mkdir(parents=True);core.write(OUT/'protocol.json',dict(contract,system=core.SYSTEM));core.write(OUT/'demands.json',data)
 class OfflineClient:
  def __init__(self,output,system,model):self.output=output;self.records=[];self.episode_http=0;core.write(output/'calls.json',[])
  def reset_episode(self):self.episode_http=0
  def generate(self,context,count,identity,stage):
   assert identity['group'] in runner.METHODS and identity['scenario']=='shock'
   self.episode_http+=1;assert self.episode_http<=16
   self.records.append(dict(**identity,stage=stage,attempt=1,status='offline_fixture',network_requests=0));core.write(self.output/'calls.json',self.records)
   deltas=('1','-1','2') if stage=='initial' else ('-2',)
   return [dict(id=f"event{identity['event']}_{stage}_{i}",rule={'rules':[{'when':'True','delta':deltas[i]}]},compiled=core.compile_rule({'rules':[{'when':'True','delta':deltas[i]}]})) for i in range(count)]
 core.Client=OfflineClient
 def forbidden(*a,**kw):raise RuntimeError('Networking forbidden in fixture')
 socket.socket=forbidden
 options=argparse.Namespace(input_file=inp,operator_library=core.LIBRARY,training_directory=core.training(11),phase='development')
 try:
  core.evaluate(options,OUT,contract,data)
  auditor=runner.module('sundial_fixture_explicit_audit',runner.HERE/'audit.py');result=auditor.audit(runner,OUT,data,contract['expected_parameter_sha256'],True)
  # Independently re-run one recorded causal forecast before paid use.
  score=next(r for r in core.read(OUT/'scores.json') if r['group']=='native_sundial' and 'forecast_audit' in r);a=score['forecast_audit'];v=a['prediction']
  raw,seeds=runner.predictor.sample_blocks(v['block_history'],len(v['raw_blocks'][0]),a['stream_identity'])
  import numpy as np
  assert np.array_equal(raw,np.asarray(v['raw_blocks'])) and seeds==v['sampling_seeds']
  core.write(OUT/'preflight_passed.json',dict(**result,network_requests=0,prompt_client_identical=True,recorded_sundial_inference_reproduced=True,not_performance_evidence=True))
  print('SUNDIAL_FULL_DEPLOYMENT_FIXTURE_PASSED',flush=True)
 except Exception as e:
  core.write(OUT/'preflight_failed.json',dict(error=type(e).__name__,detail=str(e),preserved=True,network_requests=0));raise
if __name__=='__main__':run()
