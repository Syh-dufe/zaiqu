"""No-API loading/causal replay audit of all five frozen IPPO best policies."""
import csv
import json
import math
import os
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from frozen import ROOT,read,digest,load,parameter_hash

UPSTREAM=ROOT/'external/liu-inventory'
OUTPUT=ROOT/'results/joint_baseline/interface_v1'
INPUT=ROOT/'results/online_llm_shock_types/confirmation_v5b/inputs/batch01.json'
DOCS=[ROOT/'docs/superpowers/specs/2026-10-05-joint-baseline-design.md',
      ROOT/'docs/superpowers/plans/2026-10-05-joint-baseline-interface.md']


def write(path,value):
    path.write_text(json.dumps(value,indent=2),encoding='utf-8')


def main():
    if OUTPUT.exists():raise RuntimeError('Preserve previous registration; no blind rerun')
    models={str(seed):load('ippo',seed)[1] for seed in range(11,16)}
    paths=list(Path(__file__).parent.glob('*.py'))+DOCS+[INPUT]
    paths+=list(UPSTREAM.rglob('*.py'))+list((UPSTREAM/'test_data/test_demand_merton').glob('*'))
    paths+=[ROOT/'experiments/deepseek_refinement/reports.py']
    hashes={str(p):digest(p) for p in paths}
    for p in paths:
        if p.suffix=='.py':compile(p.read_bytes(),str(p),'exec')
    OUTPUT.mkdir(parents=True)
    write(OUTPUT/'manifest.json',dict(phase='interface_compatibility_only',development_only=True,
        new_test_inputs=False,seeds=list(range(11,16)),api_calls=0,training_updates=0,
        expected_normal_validation_episodes=100,expected_replay_episodes=40,expected_recorded_node_periods=24000,
        sources_and_inputs=hashes,models=models,input_file=str(INPUT)))
    def verify():
        assert all(digest(Path(p))==sha for p,sha in hashes.items())
        assert all(digest(Path(p))==sha for c in models.values() for p,sha in c['hashes'].items())
    try:
        evaluate(models,verify)
    except Exception as exc:
        write(OUTPUT/'failed.json',dict(type=type(exc).__name__,error=str(exc),preserved=True,api_calls=0))
        raise


def evaluate(models,verify):
    sys.path.insert(0,str(UPSTREAM));os.chdir(UPSTREAM)
    sys.path.insert(0,str(ROOT/'experiments/deepseek_refinement'))
    from reports import DemandReports
    import numpy as np
    import torch
    from envs.env_wrappers import DummyVecEnv
    from runners.separated.runner import CRunner
    torch.set_num_threads(1);torch.manual_seed(11)
    data=read(INPUT);rows=[];episodes=[];checks=[];started=time.perf_counter()

    class RecordingEnv(DummyVecEnv):
        recording=False
        def reset(self):
            self.trace=self.env_list[0].eval_index;self.report=DemandReports(3);self.local=[]
            return super().reset()
        def step(self,actions):
            if not self.recording:return super().step(actions)
            env=self.env_list[0];period=env.step_num;public=self.report.public_state()
            assert public['observed_periods']==period and public['delivered_through_period']==period//3*3
            proposed=[int(np.argmax(a)) for a in actions[0]]
            assert all(0<=a<=20 for a in proposed)
            output=super().step(actions)
            demand=int(env.get_demand()[0]);assert demand==data[self.scenario][self.trace][period]
            delivered=self.report.observe(demand,env.step_num)
            if delivered:assert env.step_num%3==0
            for node in range(3):
                cost=-float(output[1][0,node,0]);assert cost==env.inventory[node]+env.backlog[node]
                row=dict(seed=self.seed,algorithm='ippo',scenario=self.scenario,trace=self.trace,
                         period=period+1,node=node,demand=demand,inventory=int(env.inventory[node]),
                         backlog=int(env.backlog[node]),cost=cost,proposed_order=proposed[node],actual_order=proposed[node],
                         delivered_through_before_action=public['delivered_through_period'],
                         notification=bool(self.scenario=='shock' and period==data['events'][self.trace]['start_index']+2))
                rows.append(row);self.local.append(row)
            if env.step_num==200:
                assert len(self.local)==600
                episodes.append(dict(seed=self.seed,scenario=self.scenario,trace=self.trace,
                    cost=float(np.mean([r['cost'] for r in self.local])),
                    downstream_backlog=float(np.mean([r['backlog'] for r in self.local if r['node']==0]))))
            return output

    for seed in range(11,16):
        verify();args,contract=load('ippo',seed)
        envs=RecordingEnv(args);envs.seed=seed
        runner=CRunner(dict(all_args=args,envs=envs,eval_envs=envs,num_agents=3,
                           device=torch.device('cpu'),run_dir=OUTPUT/f'seed{seed}_load'))
        before=parameter_hash(runner.policy);assert before==contract['expected_parameter_sha256']
        assert all(buffer.share_obs.shape[-1]==buffer.obs.shape[-1]==7 for buffer in runner.buffer)
        reward,_=runner.eval();cost=-float(reward)
        assert envs.get_eval_num()==20 and math.isclose(cost,contract['expected_normal_validation_cost'],abs_tol=1e-8,rel_tol=0)
        envs.recording=True
        for scenario in ('base','shock'):
            env=envs.env_list[0];env.eval_data=data[scenario];env.n_eval=4;env.eval_index=0;env.record_act_sta=[[],[],[]]
            envs.scenario=scenario
            reward,_=runner.eval()
            local=[e for e in episodes if e['seed']==seed and e['scenario']==scenario]
            assert len(local)==4 and math.isclose(-float(reward),np.mean([e['cost'] for e in local]),abs_tol=1e-9)
        after=parameter_hash(runner.policy);assert after==before
        checks.append(dict(seed=seed,normal_validation_cost=cost,expected_cost=contract['expected_normal_validation_cost'],
                           original_validation_episodes=20,replay_episodes=8,critic_dim=7,before=before,after=after,unchanged=True))
        runner.writter.close();envs.close();verify()
        write(OUTPUT/'progress.json',dict(completed_seeds=[c['seed'] for c in checks],api_calls=0))
        print('IPPO_INTERFACE_PASSED',seed,flush=True)
    assert len(rows)==24000 and len(episodes)==40 and sum(c['original_validation_episodes'] for c in checks)==100
    identities={(r['seed'],r['scenario'],r['trace'],r['period'],r['node']) for r in rows};assert len(identities)==24000
    for seed in range(11,16):
        for trace in range(4):
            end=data['events'][trace]['start_index']+1
            prefixes=[[ (r['actual_order'],r['cost']) for r in rows if r['seed']==seed and r['trace']==trace and r['scenario']==scenario and r['period']<end] for scenario in ('base','shock')]
            assert prefixes[0]==prefixes[1]
    with (OUTPUT/'periods.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write(OUTPUT/'episodes.json',episodes);write(OUTPUT/'model_checks.json',checks)
    verify()
    write(OUTPUT/'completed.json',dict(status='passed',normal_validation_episodes=100,replay_episodes=40,
        total_episodes=140,recorded_node_periods=24000,api_calls=0,training_updates=0,all_models_unchanged=True,
        all_costs_I_plus_B=True,report_interval=3,notification_delay=2,original_normal_costs_reproduced=True,
        wall_seconds=time.perf_counter()-started,development_only=True,
        interpretation='Frozen IPPO compatibility on original validation and previously used replay paths, not new test evidence'))


if __name__=='__main__':main()
