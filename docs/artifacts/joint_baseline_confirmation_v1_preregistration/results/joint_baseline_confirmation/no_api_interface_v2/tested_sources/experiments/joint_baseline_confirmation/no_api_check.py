"""Offline integration fixture on exposed paths; never network or new test inputs."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
import analyze

spec=importlib.util.spec_from_file_location('joint_fixture_runner',HERE/'run_online.py')
core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)
OUTPUT=ROOT/'results/joint_baseline_confirmation/no_api_interface_v2'
INPUT=ROOT/'results/online_llm_shock_types/confirmation_v5b/inputs/batch01.json'


class OfflineClient:
    def __init__(self,output,system,model):
        self.output=output;self.records=[];self.episode_http=0
        core.write(output/'calls.json',[])
    def reset_episode(self):self.episode_http=0
    def generate(self,context,count,identity,stage):
        assert identity['group']=='online_feedback' and identity['scenario']=='shock'
        assert self.episode_http<16
        self.episode_http+=1
        rule={'rules':[{'when':'True','delta':'0'}]}
        self.records.append(dict(**identity,stage=stage,attempt=1,status='offline_fixture',network_requests=0))
        core.write(self.output/'calls.json',self.records)
        return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=rule,compiled=core.compile_rule(rule)) for i in range(count)]


def main():
    if OUTPUT.exists():raise RuntimeError('Offline fixture output already exists; preserve it')
    for path in HERE.glob('*.py'):compile(path.read_bytes(),str(path),'exec')
    original_spec=importlib.util.spec_from_file_location('joint_original_runner',ROOT/'experiments/demand_shock_confirmation_v5/run_online.py')
    original=importlib.util.module_from_spec(original_spec);original_spec.loader.exec_module(original)
    assert core.SYSTEM==original.SYSTEM and core.Client is original.Client and core.EventController is original.EventController
    contracts={str(seed):core.contracts(INPUT,core.LIBRARY,core.training(seed),require_key=False) for seed in range(11,16)}
    OUTPUT.mkdir(parents=True)
    core.write(OUTPUT/'manifest.json',dict(development_only=True,offline_fixture_only=True,new_inputs=False,
        input=str(INPUT),api_requests=0,simulated_response='valid zero corrections',contracts=contracts,
        original_prompt_client_controller_identical=True,not_a_performance_experiment=True))
    before=core.source_hashes();core.Client=OfflineClient
    try:
        for seed in (11,12,13,14,15):
            out=OUTPUT/f'seed{seed}';out.mkdir()
            opts=argparse.Namespace(input_file=INPUT,operator_library=core.LIBRARY,training_directory=core.training(seed))
            # Real contracts compare key presence; no credential is needed or sent
            # by the offline replacement. Suppress only the presence requirement.
            original_contracts=core.contracts
            def offline_contracts(*args,**kw):
                kw['require_key']=False
                return original_contracts(*args,**kw)
            core.contracts=offline_contracts
            try:core.evaluate(opts,out,contracts[str(seed)],core.read(INPUT))
            finally:core.contracts=original_contracts
            with (out/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
            done=core.read(out/'completed.json');episodes=core.read(out/'episodes.json')
            audit=analyze.audit_raw(rows,episodes,core.read(INPUT),core.read(out/'information_audits.json'),done['parameter_checks'],contracts[str(seed)])
            reference=core.read(ROOT/'results/joint_baseline/interface_v1/episodes.json')
            # Existing independent IPPO replay supplies a non-LLM cost oracle.
            previous=[e for e in reference if e.get('seed')==seed and e.get('scenario') in ('base','shock')]
            assert len(previous)==8
            for e in episodes:
                if e['group']=='ippo':
                    old=next(x for x in previous if x['scenario']==e['scenario'] and x['trace']==e['trace'])
                    assert abs(e['cost']-old['cost'])<1e-9
            # Reject corruption rather than weakening a production audit.
            bad=[dict(r) for r in rows];bad[0]['cost']=str(float(bad[0]['cost'])+1)
            try:analyze.audit_raw(bad,episodes,core.read(INPUT),core.read(out/'information_audits.json'),done['parameter_checks'],contracts[str(seed)])
            except AssertionError:pass
            else:raise AssertionError('Cost corruption was not rejected')
            core.write(out/'offline_audit.json',dict(**audit,api_requests=0,IPPO_replay_cost_oracle=True,cost_corruption_rejected=True,
                controller_dispatch='IPPO pure HAPPO controller branch; online_feedback original controller with mock zero response',
                source_sha256=before))
        assert core.source_hashes()==before
        # Constant differences have constant intervals at either registered level.
        values={t:__import__('numpy').full((10,5,len(analyze.METRICS)),-1.) for t in analyze.TYPES}
        result=analyze.crossed(values,.975)
        assert all(x['mean']==x['low']==x['high']==-1 for x in result['overall'].values())
        core.write(OUTPUT/'completed.json',dict(status='passed',api_requests=0,training_updates=0,episodes=120,
            unique_node_periods=72000,all_five_seed_dispatch_audited=True,constant_bootstrap_oracle=True,
            original_prompt_client_controller_identical=True,development_only=True))
    except Exception as exc:
        core.write(OUTPUT/'failed.json',dict(error=type(exc).__name__,detail=str(exc),api_requests=0,preserved=True))
        raise


if __name__=='__main__':main()
