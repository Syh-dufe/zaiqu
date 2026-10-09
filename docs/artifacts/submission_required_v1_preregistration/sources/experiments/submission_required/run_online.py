"""Frozen HAPPO/IPPO and original online LLM common-path confirmation."""
import argparse
import ast
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT/'external/liu-inventory'
sys.path.insert(0,str(ROOT/'experiments/deepseek_refinement'))
sys.path.insert(0,str(ROOT/'experiments/formal_evaluation'))
from shadow import features, snapshot, clone, compile_rule
from reports import DemandReports
from ablations import random_rules
# Import our siblings explicitly before adding the author's source tree.
sys.path.insert(0,str(ROOT/'experiments/online_llm'))
from client import Client, FatalAPIError, write
from controller import EventController
# Isolated component variants; full strategy remains the original class.
sys.path.insert(0,str(Path(__file__).parent))
from component import ControllerFactory
EventController=ControllerFactory

sys.path.insert(0,str(ROOT/'experiments/joint_baseline'))
import frozen

METHODS = ('happo','online_feedback','no_feedback','no_review','first_only','deterministic_search')
LIBRARY = ROOT/'docs/artifacts/operator_discovery_v1/repaired_library.json'
system_tree = ast.parse((ROOT/'experiments/deepseek_refinement/run.py').read_text(encoding='utf-8'))
SYSTEM = next(ast.literal_eval(n.value) for n in system_tree.body if isinstance(n,ast.Assign)
              and any(isinstance(t,ast.Name) and t.id=='SYSTEM' for t in n.targets)) + '''
Report interval3: each delivered report aggregates3 completed external demands. The demand_mean is repeated3 times only as a reconstruction, never exact within-block demand. Node0 incoming/recent/baseline use delivered reconstruction. Upstream incoming is last executed downstream order. Current inventory, backlog, every pipeline slot, previous orders and current HAPPO proposal are visible. Emergency notification gives no start, magnitude or end. Memory resets each episode and contains only already observed states/orders/delivered reports. Observation changes do not prove a correction caused them. Search feedback is uncertain synthetic prediction; independent review is never supplied to you. Return exactly requested candidate count, one to four valid DSL rules each. This synchronous30-second HTTP timeout is not a real-world execution deadline guarantee.'''


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def training(seed):
    return ROOT/'results/learning_curve'/('curve_seed11_until_stable_v1' if seed==11 else f'curve_seed{seed}_formal_v1')


def load_policy(algorithm,seed):
    if algorithm=='ippo':return frozen.load(algorithm,seed)
    directory=training(seed)
    done=read(directory/'completed.json');audit=read(directory/'completion_audit.json')
    cfg=read(directory/'config.json')['config']
    assert cfg['seed']==[seed] and cfg['use_centralized_V'] and done['seed']==seed
    assert done['best_scheduled_evaluation']['step'] in audit['model_matches']['official_best']['matching_steps']
    model_dir=Path(done['final_model_directory']).parent/'models'
    files=[directory/n for n in ('config.json','completed.json','completion_audit.json')]
    files += [model_dir/f'{label}_agent{i}.pt' for i in range(3) for label in ('actor','critic')]
    contract=dict(algorithm='happo',seed=seed,expected_parameter_sha256=audit['model_matches']['official_best']['sha256'],
                  expected_normal_validation_cost=done['official_best_cost'],critic_dim=21,
                  hashes={str(p):digest(p) for p in files},model_directory=str(model_dir))
    args=argparse.Namespace(**cfg);args.model_dir=str(model_dir)
    return args,contract


def validate_inputs(data):
    if any(len(data.get(k,[]))!=4 for k in ('base','shock','events')):
        raise ValueError('Exactly four registered traces required')
    # Legacy input is used only to compare frozen model/source metadata before
    # registering the new profiles; evaluated inputs always carry a type.
    if all('type' not in event for event in data['events']):
        for base,shock,event in zip(data['base'],data['shock'],data['events']):
            if len(base)!=201 or len(shock)!=201 or any(type(v) is not int or not 0<=v<=20 for v in base+shock):
                raise ValueError('Expected201 bounded integer demands')
            start,duration,intensity=event['start_index'],event['duration'],event['intensity']
            if type(start) is not int or type(duration) is not int or not 60<=start<=100 or not 20<=duration<=40 or intensity not in (1.25,1.5):
                raise ValueError('Invalid legacy shock event')
            expected=[min(20,math.ceil(intensity*v)) if start<=i<start+duration else v for i,v in enumerate(base)]
            if shock!=expected:raise ValueError('Legacy shock differs from its registered transformation')
        if sorted(e['intensity'] for e in data['events'])!=[1.25,1.25,1.5,1.5]:
            raise ValueError('Legacy reference needs two traces per intensity')
        if len({tuple(t[:200]) for t in data['base']})!=4:raise ValueError('Duplicate consumed legacy demand within batch')
        return data
    for base,shock,event in zip(data['base'],data['shock'],data['events']):
        if len(base)!=201 or len(shock)!=201 or any(type(v) is not int or not 0<=v<=20 for v in base+shock):
            raise ValueError('Expected201 bounded integer demands')
        start,duration = event['start_index'],event['duration']
        if type(start) is not int or type(duration) is not int or not 40<=start<=120 or not 20<=duration<=80:
            raise ValueError('Event envelope outside registered range')
        if event.get('type') not in ('single_surge','sustained_surge','double_surge','surge_then_drop'):
            raise ValueError('Unregistered shock type')
        expected=base.copy()
        intervals=event.get('intervals')
        if not isinstance(intervals,list) or not intervals:
            raise ValueError('Shock intervals are required')
        for interval in intervals:
            left,right,factor=interval['start'],interval['end'],interval['factor']
            if type(left) is not int or type(right) is not int or not 0<=left<right<=200:
                raise ValueError('Invalid shock interval')
            if factor not in (0.5,1.10,1.25,1.5):
                raise ValueError('Invalid registered factor')
            for i in range(left,right):
                scaled=factor*base[i]
                expected[i]=min(20,math.ceil(scaled)) if factor>1 else math.floor(scaled)
        if shock!=expected:
            raise ValueError('Shock differs from its registered piecewise transformation')
        if event['start_index']!=min(x['start'] for x in intervals) or event['duration']!=max(x['end'] for x in intervals)-event['start_index']:
            raise ValueError('Shock envelope does not match intervals')
        if base[:event['start_index']]!=shock[:event['start_index']]:
            raise ValueError('Demand changed before the first emergency notification')
    if len({tuple(t[:200]) for t in data['base']})!=4:
        raise ValueError('Duplicate consumed demand within batch')
    return data


def source_hashes():
    files = list(Path(__file__).parent.glob('*.py')) + [ROOT/'experiments/joint_baseline_confirmation/run_online.py',ROOT/'docs/superpowers/specs/2026-10-09-required-experiments-design.md',ROOT/'docs/superpowers/plans/2026-10-09-required-experiments.md'] + [ROOT/f'experiments/deepseek_refinement/{n}' for n in ('run.py','shadow.py','reports.py')]
    files += [ROOT/'experiments/deepseek_pilot/rules.py',ROOT/'experiments/formal_evaluation/ablations.py']
    files += [ROOT/f'experiments/online_llm/{n}' for n in ('run.py','client.py','controller.py')]
    files += [ROOT/'experiments/joint_baseline/frozen.py',
              ROOT/'docs/superpowers/plans/2026-10-05-joint-baseline-confirmation.md',
              ROOT/'docs/superpowers/specs/2026-10-05-joint-baseline-design.md']
    files += list(UPSTREAM.rglob('*.py'))
    return {str(p.relative_to(ROOT)):digest(p) for p in files}


def contracts(input_file,library_path,training_directory,require_key=True):
    data=validate_inputs(read(input_file))
    values=read(library_path)['candidates']
    if len(values)!=3:
        raise ValueError('Old fixed library must have3 candidates')
    for value in values:
        compile_rule(value)
    audit=read(training_directory/'completion_audit.json')
    done=read(training_directory/'completed.json')
    config=read(training_directory/'config.json')['config']
    if config['seed']!=[done['seed']] or config['episode_length']!=200 or config['n_eval_rollout_threads']!=1:
        raise ValueError('Frozen training/evaluation metadata contract differs')
    models=Path(done['final_model_directory']).parent/'models'
    if not models.is_dir() or not list(models.glob('*')):
        raise ValueError('Frozen model directory missing')
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=UPSTREAM,text=True).strip()
    if revision!='a7e5a3e83e21565a5799483bc534e39635ec65dd' or subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=UPSTREAM,text=True).strip():
        raise ValueError('Author source differs from pinned clean revision')
    if require_key and not os.environ.get('DEEPSEEK_API_KEY'):
        raise ValueError('DEEPSEEK_API_KEY missing')
    _,ippo_contract=load_policy('ippo',done['seed'])
    _,happo_contract=load_policy('happo',done['seed'])
    assert happo_contract['expected_parameter_sha256']==audit['model_matches']['official_best']['sha256']
    return dict(ippo_contract=ippo_contract,happo_contract=happo_contract,input_sha256=digest(input_file),library_sha256=digest(library_path),source_sha256=source_hashes(),
        expected_parameter_sha256=audit['model_matches']['official_best']['sha256'],
        model_files={str(p):digest(p) for p in models.rglob('*') if p.is_file()},
        training_metadata={n:digest(training_directory/n) for n in ('config.json','completed.json','completion_audit.json')},
        upstream_revision=revision,key_present=bool(os.environ.get('DEEPSEEK_API_KEY')),
        training_seed=done['seed'],
        model=os.environ.get('DEEPSEEK_MODEL','deepseek-flash'),traces=4,consumed_indices=[0,199],
        methods=list(METHODS),report_interval=3,correction_periods=5,forecast_horizon=20,
        candidate_count=3,search_paths=3,review_paths=3,max_events=4,max_http_per_episode=16,
        synchronous_timeout_seconds=30,real_world_deadline_guaranteed=False,
        development_only=False,independent_confirmation=True)


def main():
    global METHODS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name',required=True)
    parser.add_argument('--input-file',type=Path,required=True)
    parser.add_argument('--training-directory',type=Path,default=training(11))
    parser.add_argument('--operator-library',type=Path,default=LIBRARY)
    parser.add_argument('--output-root',type=Path,default=ROOT/'results/online_llm')
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--methods',nargs='+',choices=METHODS,default=list(METHODS))
    parser.add_argument('--phase',choices=('development','confirmation','sensitivity'),default='development')
    opts=parser.parse_args()
    METHODS=tuple(opts.methods)
    if not opts.run_name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in opts.run_name):
        parser.error('Invalid run name')
    opts.input_file=opts.input_file.resolve();opts.training_directory=opts.training_directory.resolve();opts.operator_library=opts.operator_library.resolve()
    contract=contracts(opts.input_file,opts.operator_library,opts.training_directory)
    if opts.preflight:
        print(json.dumps(contract,ensure_ascii=False,indent=2));return
    out=opts.output_root.resolve()/opts.run_name
    if out.exists():
        raise RuntimeError('Refuse overwrite')
    out.mkdir(parents=True)
    write(out/'protocol.json',dict(contract,phase=opts.phase,system=SYSTEM,options={k:str(v) if isinstance(v,Path) else v for k,v in vars(opts).items()}))
    data=validate_inputs(read(opts.input_file));write(out/'demands.json',data)
    try:
        evaluate(opts,out,contract,data)
    except Exception as exc:
        write(out/'failed.json',dict(failure=type(exc).__name__,detail=str(exc)[:1000],original_outputs_preserved=True))
        raise


def evaluate(opts,out,contract,data):
    sys.path.insert(0,str(UPSTREAM));os.chdir(UPSTREAM)
    import numpy as np
    import torch
    from envs.env_wrappers import DummyVecEnv
    from runners.separated.runner import CRunner
    torch.set_num_threads(1);torch.manual_seed(11)
    config=read(opts.training_directory/'config.json')['config']
    done=read(opts.training_directory/'completed.json')
    model_dir=Path(done['final_model_directory']).parent/'models'
    library=[dict(id=f'library_{i}',rule=r,compiled=compile_rule(r)) for i,r in enumerate(read(opts.operator_library)['candidates'])]
    client=Client(out,SYSTEM,contract['model'])
    rows=[];episodes=[];scores=[];checks={};failures=[];information=[];deliveries=[]
    started=time.perf_counter()

    def model_hash(policies):
        value=hashlib.sha256()
        for policy in policies:
            for net in (policy.actor,policy.critic):
                for name,tensor in net.state_dict().items():
                    value.update(name.encode());value.update(tensor.detach().cpu().numpy().tobytes())
        return value.hexdigest()

    class Controller(DummyVecEnv):
        def reset(self):
            self.trace=self.env_list[0].eval_index
            self.history=[];self.orders=[];self.recurrent=[None]*3;self.episode_rows=[]
            self.reports=DemandReports(3)
            self.event_controller=EventController('happo' if self.group=='ippo' else self.group,client,library,random_rules,dict(group=self.group,scenario=self.scenario,trace=self.trace))
            return super().reset()

        def step(self,actions):
            env=self.env_list[0];period=env.step_num
            proposed=[int(np.argmax(a)) for a in actions[0]]
            report_state=self.reports.public_state()
            assert report_state['observed_periods']==period and report_state['delivered_through_period']==period//3*3
            notify=self.scenario=='shock' and period==data['events'][self.trace]['start_index']+2
            actual,record=self.event_controller.decide(env,self.history,self.orders,proposed,self.recurrent,self.actors,self.reports,notify)
            if record and record.get('execution_failure'):
                failures.append(dict(group=self.group,scenario=self.scenario,trace=self.trace,period=period+1,
                                     failure=record['execution_failure'],selected_before_execution=record['selected_before_execution']))
            if record:
                scores.append(record);write(out/'scores.json',scores)
            information.append(dict(group=self.group,scenario=self.scenario,trace=self.trace,decision_period=period+1,
                **report_state,chosen=self.event_controller.chosen,rule_features=features(env,self.reports.delivered_history,self.orders,proposed)))
            state=snapshot(env,self.history)
            output=super().step([[np.eye(21)[a] for a in actual]])
            demand=int(env.get_demand()[0]);self.history.append(demand);self.orders.append(actual.copy())
            report=self.reports.observe(demand,env.step_num)
            if report:
                deliveries.append(dict(group=self.group,scenario=self.scenario,trace=self.trace,**report))
            observed_clone=clone(state,self.history[:-1],[demand]);observed_clone.step(actual,one_hot=False)
            assert observed_clone.inventory==env.inventory and observed_clone.backlog==env.backlog and observed_clone.order==env.order
            for node in range(3):
                row=dict(group=self.group,scenario=self.scenario,trace=self.trace,period=env.step_num,node=node,demand=demand,
                    cost=-float(output[1][0,node,0]),inventory=int(env.inventory[node]),backlog=int(env.backlog[node]),
                    policy_order=proposed[node],actual_order=actual[node],chosen=self.event_controller.chosen,
                    notification_period=None if self.event_controller.notification is None else self.event_controller.notification+1)
                rows.append(row);self.episode_rows.append(row)
            if env.step_num==200:
                episodes.append(dict(group=self.group,scenario=self.scenario,trace=self.trace,
                    cost=float(np.mean([r['cost'] for r in self.episode_rows])),
                    downstream_backlog=float(np.mean([r['backlog'] for r in self.episode_rows if r['node']==0])),
                    generation_events=self.event_controller.events,episode_http=client.episode_http,
                    notification_period=None if self.event_controller.notification is None else self.event_controller.notification+1))
                write(out/'episodes.json',episodes)
                write(out/'information_audits.json',information);write(out/'delivered_reports.json',deliveries)
                write(out/'runtime_failures.json',failures)
                with (out/'periods.csv').open('w',newline='',encoding='utf-8') as stream:
                    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
                print('EPISODE',episodes[-1],flush=True)
            return output

    for group in METHODS:
        assert contracts(opts.input_file,opts.operator_library,opts.training_directory)==contract,'Frozen contracts changed before method'
        algorithm='ippo' if group=='ippo' else 'happo'
        args,group_contract=load_policy(algorithm,contract['training_seed'])
        expected=contract['ippo_contract' if algorithm=='ippo' else 'happo_contract']
        assert group_contract==expected
        envs=Controller(args)
        runner=CRunner(dict(all_args=args,envs=envs,eval_envs=envs,num_agents=3,device=torch.device('cpu'),run_dir=out/group))
        before=model_hash(runner.policy)
        assert before==expected['expected_parameter_sha256']
        envs.actors=[]
        for i,policy in enumerate(runner.policy):
            original=policy.act;envs.actors.append(original)
            def capture(*a,_original=original,_i=i,**kw):
                result=_original(*a,**kw);envs.recurrent[_i]=result[1].detach().cpu().numpy().copy();return result
            policy.act=capture
        for scenario in ('base','shock'):
            env=envs.env_list[0];env.eval_data=data[scenario];env.n_eval=4;env.eval_index=0;env.record_act_sta=[[],[],[]]
            envs.group=group;envs.scenario=scenario
            reward,_=runner.eval()
            local=[e for e in episodes if e['group']==group and e['scenario']==scenario]
            assert math.isclose(-float(reward),np.mean([e['cost'] for e in local]),abs_tol=1e-9)
        after=model_hash(runner.policy);assert before==after
        checks[group]=dict(before=before,after=after,unchanged=True)
        runner.writter.close();envs.close()
    assert len(episodes)==len(METHODS)*8 and len(rows)==len(METHODS)*4800
    assert len({(r['group'],r['scenario'],r['trace'],r['period'],r['node']) for r in rows})==len(METHODS)*4800
    for trace in range(4):
        events=[r for r in scores if r['group']=='online_feedback' and r['trace']==trace and r.get('generation_event')]
        assert len(events)<=4
        assert all(len(r['candidates'])==4 and len(r['search_revision_feedback'])==4 for r in events)
        for group in METHODS:
            episode=next(e for e in episodes if e['group']==group and e['scenario']=='shock' and e['trace']==trace)
            assert episode['episode_http']<=16
    for scenario in ('base','shock'):
        for trace in range(4):
            end=201 if scenario=='base' else data['events'][trace]['start_index']+3
            reference=[(r['cost'],r['actual_order']) for r in rows if r['group']=='happo' and r['scenario']==scenario and r['trace']==trace and r['period']<end]
            for group in [m for m in METHODS if m!='happo']:
                assert reference==[(r['cost'],r['actual_order']) for r in rows if r['group']==group and r['scenario']==scenario and r['trace']==trace and r['period']<end]
    for trace,event in enumerate(data['events']):
        for group in METHODS:
            left=[(r['cost'],r['actual_order']) for r in rows if r['group']==group and r['scenario']=='base' and r['trace']==trace and r['period']<=event['start_index']]
            right=[(r['cost'],r['actual_order']) for r in rows if r['group']==group and r['scenario']=='shock' and r['trace']==trace and r['period']<=event['start_index']]
            assert left==right,'Own normal/shock prefix differs'
    assert source_hashes()==contract['source_sha256'],'Frozen source changed during evaluation'
    assert digest(opts.input_file)==contract['input_sha256'] and digest(opts.operator_library)==contract['library_sha256']
    assert contracts(opts.input_file,opts.operator_library,opts.training_directory)==contract,'Frozen model or metadata changed'
    write(out/'completed.json',dict(episodes=len(episodes),rows=len(rows),training_updates=0,parameter_checks=checks,
        calls=len(client.records),runtime_failures=failures,wall_seconds=time.perf_counter()-started,
        development_only=opts.phase=='development',independent_confirmation=opts.phase=='confirmation',phase=opts.phase,
        causal_audit='Public whitelist; episode reset; synthetic-only forecast; no review in prompts'))
    print('ONLINE_DRAFT_COMPLETED',flush=True)


if __name__=='__main__':
    main()
