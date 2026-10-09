"""No-network real deployment fixture, using exposed data and simulated valid API output."""
import argparse
from pathlib import Path
import socket
import sys
from common import ROOT,HERE,OUTPUT,METHODS,module,read,write,training
from audit import audit

def run():
    root=OUTPUT/'offline_fixture'
    if root.exists():raise RuntimeError('Preserve existing offline fixture')
    for p in HERE.glob('*.py'):compile(p.read_bytes(),str(p),'exec')
    core=module('required_fixture_runner',HERE/'run_online.py')
    original=module('required_original_runner',ROOT/'experiments/joint_baseline_confirmation/run_online.py')
    assert core.SYSTEM==original.SYSTEM and core.Client is original.Client
    assert core.EventController('online_feedback',None,[],None,{}).__class__ is original.EventController
    assert core.EventController('happo',None,[],None,{}).__class__ is original.EventController
    # These constructors are independent, with cleared local memory.
    for m in METHODS:
        c=core.EventController(m,None,[],None,{})
        assert c.events==0 and c.memory==[] and c.notification is None and c.chosen=='zero'
    input_file=ROOT/'results/joint_baseline_confirmation/confirmation_v1/inputs/batch01.json'
    contract=core.contracts(input_file,core.LIBRARY,training(11),require_key=False)
    root.mkdir(parents=True);write(root/'protocol.json',contract);data=read(input_file);write(root/'demands.json',data)
    class OfflineClient:
        def __init__(self,output,system,model):
            self.output=output;self.records=[];self.episode_http=0;write(output/'calls.json',[])
        def reset_episode(self):self.episode_http=0
        def generate(self,context,count,identity,stage):
            assert identity['group'] in ('online_feedback','no_feedback','no_review','first_only') and identity['scenario']=='shock'
            self.episode_http+=1;assert self.episode_http<=16
            self.records.append(dict(**identity,stage=stage,attempt=1,status='offline_fixture',network_requests=0))
            write(self.output/'calls.json',self.records)
            rule={'rules':[{'when':'True','delta':'0'}]}
            return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=rule,compiled=core.compile_rule(rule)) for i in range(count)]
    core.Client=OfflineClient
    original_contracts=core.contracts
    def offline_contracts(*args,**kw):
        kw['require_key']=False;return original_contracts(*args,**kw)
    core.contracts=offline_contracts
    # Networking is forbidden even if a code path accidentally uses a real client.
    def forbidden(*args,**kw):raise RuntimeError('Network forbidden in fixture')
    socket.socket=forbidden
    options=argparse.Namespace(input_file=input_file,operator_library=core.LIBRARY,training_directory=training(11),phase='development')
    try:
        core.evaluate(options,root,contract,data)
        result=audit(root,METHODS,data,contract['expected_parameter_sha256'],offline=True)
        # Pure frozen HAPPO costs must equal the old replay on exact same inputs.
        old=read(ROOT/'results/joint_baseline_confirmation/confirmation_v1/runs/seed11_batch01/episodes.json')
        current=read(root/'episodes.json')
        for e in current:
            if e['group']=='happo':
                prior=next(x for x in old if x['group']=='happo' and x['scenario']==e['scenario'] and x['trace']==e['trace'])
                assert abs(e['cost']-prior['cost'])<1e-9
        write(root/'preflight_passed.json',dict(**result,network_requests=0,original_happo_replay_exact=True,
            full_strategy_original_class=True,original_prompt_client_identical=True,not_performance_evidence=True))
        print('NO_API_DEPLOYMENT_FIXTURE_PASSED',flush=True)
    except Exception as e:
        write(root/'preflight_failed.json',dict(error=type(e).__name__,detail=str(e),preserved=True,network_requests=0));raise

if __name__=='__main__':run()
