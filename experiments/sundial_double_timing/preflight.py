"""All timing/method wiring with six zero-effect rules and network blocked."""
import argparse,socket
import runner
OUT=runner.ROOT/'results/sundial_double_timing/no_api_fixture_v1'
def run():
    assert not OUT.exists();OUT.mkdir(parents=True);core=runner.core;runner.configure(11)
    class Fake:
        def __init__(self,out,*a):self.records=[];self.episode_http=0;core.write(out/'calls.json',[])
        def reset_episode(self):self.episode_http=0
        def generate(self,context,count,identity,stage):
            rule={'rules':[{'when':'False','delta':'0'} for _ in range(5)]+[{'when':'True','delta':'0'}]}
            return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=rule,compiled=core.compile_rule(rule)) for i in range(count)]
    core.Client=Fake;old=core.contracts
    def contracts(*a,**kw):kw['require_key']=False;return old(*a,**kw)
    core.contracts=contracts
    import torch
    def forbidden(*a,**kw):raise RuntimeError('Network disabled in timing fixture')
    socket.socket=forbidden;socket.create_connection=forbidden
    c=core.contracts(runner.INPUT,core.LIBRARY,core.training(11));data=core.read(runner.INPUT)
    core.write(OUT/'protocol.json',dict(c,system=core.SYSTEM));core.write(OUT/'demands.json',data)
    opts=argparse.Namespace(input_file=runner.INPUT,operator_library=core.LIBRARY,training_directory=core.training(11),phase='development')
    try:
        core.evaluate(opts,OUT,c,data)
        a=runner.module('timing_explicit_audit',runner.HERE/'audit.py').audit(runner,OUT,data,c['expected_parameter_sha256'],True)
        core.write(OUT/'preflight_passed.json',dict(**a,network_requests=0,fake_zero_rules_not_performance=True));print('TIMING_FIXTURE_PASSED',flush=True)
    except Exception as e:core.write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),preserved=True));raise
if __name__=='__main__':run()
