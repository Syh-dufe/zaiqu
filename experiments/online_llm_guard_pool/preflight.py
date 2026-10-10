"""Real frozen-model deployment fixture; synthetic replies, networking forbidden."""
import argparse
import socket
from pathlib import Path
from runner import ROOT,HERE,METHODS,core,original,module
# The inherited runner changes sys.path; never resolve this auditor by a bare import.
auditor=module('guard_pool_fixture_auditor',HERE/'audit.py')
audit=auditor.audit

OUTPUT=ROOT/'results/online_llm_guard_pool/offline_fixture_v3_cached'
RUN_METHODS=('revision_guard','pool_review','guard_pool')

def run():
    if OUTPUT.exists():raise RuntimeError('Preserve existing fixture')
    assert core.EventController('online_feedback',None,[],None,{}).__class__ is original.EventController
    assert core.EventController('happo',None,[],None,{}).__class__ is original.EventController
    assert core.Client is original.Client if hasattr(original,'Client') else core.Client.__module__=='client'
    original_runner=__import__('runner').module('guard_pool_original_prompt',ROOT/'experiments/joint_baseline_confirmation/run_online.py')
    assert core.SYSTEM==original_runner.SYSTEM and core.Client is original_runner.Client
    input_file=ROOT/'results/submission_required/v1/inputs/confirmation01_main.json'
    data=core.read(input_file)
    core.METHODS=RUN_METHODS
    saved_contracts=core.contracts
    def contracts(*args,**kwargs):
        kwargs['require_key']=False;return saved_contracts(*args,**kwargs)
    core.contracts=contracts
    contract=core.contracts(input_file,core.LIBRARY,core.training(11))
    OUTPUT.mkdir(parents=True)
    core.write(OUTPUT/'protocol.json',contract);core.write(OUTPUT/'demands.json',data)
    class OfflineClient:
        def __init__(self,output,system,model):
            self.output=output;self.records=[];self.episode_http=0;core.write(output/'calls.json',[])
        def reset_episode(self):self.episode_http=0
        def generate(self,context,count,identity,stage):
            assert identity['group'] in METHODS[1:] and identity['scenario']=='shock'
            self.episode_http+=1;assert self.episode_http<=16
            self.records.append(dict(**identity,stage=stage,attempt=1,status='offline_fixture',network_requests=0))
            core.write(self.output/'calls.json',self.records)
            # Nonzero proposals exercise real prediction and execution; revision differs.
            deltas=('1','-1','2') if stage=='initial' else ('-2',)
            values=[]
            for i in range(count):
                rule={'rules':[{'when':'True','delta':deltas[i]}]}
                values.append(dict(id=f"event{identity['event']}_{stage}_{i}",rule=rule,compiled=core.compile_rule(rule)))
            return values
    core.Client=OfflineClient
    def forbidden(*args,**kwargs):raise RuntimeError('Network forbidden in fixture')
    socket.socket=forbidden
    options=argparse.Namespace(input_file=input_file,operator_library=core.LIBRARY,training_directory=core.training(11),phase='development')
    try:
        core.evaluate(options,OUTPUT,contract,data)
        cached=ROOT/'results/submission_required/v1/runs/confirmation01_main_seed11'
        result=audit(OUTPUT,data,contract['expected_parameter_sha256'],offline=True,methods=RUN_METHODS,cached=cached)
        old=core.read(ROOT/'results/submission_required/v1/runs/confirmation01_main_seed11/episodes.json')
        for episode in core.read(OUTPUT/'episodes.json'):
            if episode['group']=='happo':
                prior=next(e for e in old if e['group']=='happo' and e['scenario']==episode['scenario'] and e['trace']==episode['trace'])
                assert abs(episode['cost']-prior['cost'])<1e-9
        core.write(OUTPUT/'preflight_passed.json',dict(**result,network_requests=0,original_prompt_client_identical=True,
            original_happo_replay_exact='happo' in RUN_METHODS,full_original_controller_identity=True,not_performance_evidence=True))
        print('GUARD_POOL_REAL_DEPLOYMENT_FIXTURE_PASSED',flush=True)
    except Exception as exc:
        core.write(OUTPUT/'preflight_failed.json',dict(error=type(exc).__name__,detail=str(exc),preserved=True,network_requests=0));raise

if __name__=='__main__':run()
