"""Boolean case-only comparison with original event behavior for all LLM methods."""
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
import importlib.util

def load_module(name,path):
    if name in sys.modules:
        module=sys.modules[name]
        if Path(module.__file__).resolve()!=path.resolve():
            raise RuntimeError('Module alias collision: '+name)
        return module
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

for sibling in ('client','controller'):
    cached=sys.modules.get(sibling)
    expected=ROOT/'experiments/online_llm'/f'{sibling}.py'
    if cached is not None and Path(cached.__file__).resolve()!=expected:
        raise RuntimeError('Original sibling import collision: '+sibling)

BASE=load_module('case_only_original_run',ROOT/'experiments/online_llm/run.py')
CLIENT=load_module('case_only_client_impl',Path(__file__).with_name('client.py'))
CONTROL=load_module('case_only_controller_impl',Path(__file__).with_name('controller.py'))
features,snapshot,clone,compile_rule=BASE.features,BASE.snapshot,BASE.clone,BASE.compile_rule
DemandReports=BASE.DemandReports
write=CLIENT.write
METHODS=('happo','online_feedback','case_feedback')
LIBRARY=BASE.LIBRARY
SYSTEM=BASE.SYSTEM
SYSTEMS=dict(online_feedback=SYSTEM,case_feedback=SYSTEM)
REFERENCE=ROOT/'docs/artifacts/online_llm_neutral_development_v3/inputs.json'
REFERENCE_MANIFEST=REFERENCE.with_name('manifest.json')
sys.modules.setdefault('case_only_run_core',sys.modules[__name__])


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def training(seed):
    return ROOT/'results/learning_curve'/('curve_seed11_until_stable_v1' if seed==11 else f'curve_seed{seed}_formal_v1')


def validate_inputs(data):
    if any(len(data.get(k,[]))!=4 for k in ('base','shock','events')):
        raise ValueError('Exactly four registered traces required')
    for base,shock,event in zip(data['base'],data['shock'],data['events']):
        if len(base)!=201 or len(shock)!=201 or any(type(v) is not int or not 0<=v<=20 for v in base+shock):
            raise ValueError('Expected201 bounded integer demands')
        start,duration,intensity = event['start_index'],event['duration'],event['intensity']
        if type(start) is not int or type(duration) is not int or not 60<=start<=100 or not 20<=duration<=40:
            raise ValueError('Event outside registered range')
        if intensity not in (1.25,1.5):
            raise ValueError('Invalid registered intensity')
        expected=[min(20,math.ceil(intensity*v)) if start<=i<start+duration else v for i,v in enumerate(base)]
        if shock!=expected:
            raise ValueError('Shock differs from registered transformation')
    if sorted(e['intensity'] for e in data['events'])!=[1.25,1.25,1.5,1.5]:
        raise ValueError('Need two traces per intensity')
    if len({tuple(t[:200]) for t in data['base']})!=4:
        raise ValueError('Duplicate consumed demand within batch')
    return data


def source_hashes():
    paths=list(Path(__file__).parent.glob('*.py'))+[
        ROOT/'docs/superpowers/plans/2026-10-04-online-llm-bool-case-only.md',
        REFERENCE,REFERENCE_MANIFEST,REFERENCE.with_name('freeze.json')]
    return dict(BASE.source_hashes(),**{str(p.relative_to(ROOT)):digest(p) for p in paths})



def contracts(input_file,library_path,training_directory,require_key=True):
    value=BASE.contracts(input_file,library_path,training_directory,require_key)
    value.update(source_sha256=source_hashes(),methods=list(METHODS),phase='case_only_development',
        development_only=True,v1_client_source=str(ROOT/'experiments/online_llm/client.py'),
        v1_controller_source=str(ROOT/'experiments/online_llm/controller.py'),
        v1_system_sha256=hashlib.sha256(SYSTEM.encode()).hexdigest(),
        case_system_sha256=hashlib.sha256(SYSTEM.encode()).hexdigest(),
        system_sha256_by_method={g:hashlib.sha256(s.encode()).hexdigest() for g,s in SYSTEMS.items()},
        reference_input_sha256=digest(REFERENCE),reference_manifest_sha256=digest(REFERENCE_MANIFEST),
        reused_neutral_v3_development_inputs=True,normalization='Only expression NAME true/false to True/False')
    assert digest(REFERENCE)==read(REFERENCE_MANIFEST)['input_sha256']==digest(input_file)
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name',required=True)
    parser.add_argument('--input-file',type=Path,required=True)
    parser.add_argument('--training-directory',type=Path,default=training(11))
    parser.add_argument('--operator-library',type=Path,default=LIBRARY)
    parser.add_argument('--output-root',type=Path,default=ROOT/'results/online_llm_case_only')
    parser.add_argument('--preflight',action='store_true')
    opts=parser.parse_args()
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
    write(out/'protocol.json',dict(contract,system=SYSTEM,systems_by_method=SYSTEMS,options={k:str(v) if isinstance(v,Path) else v for k,v in vars(opts).items()}))
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
    clients={group:klass(out,SYSTEMS.get(group,SYSTEM),contract['model'])
             for group,klass in (('happo',CLIENT.V1Client),('online_feedback',CLIENT.V1Client),
                                 ('case_feedback',CLIENT.CaseClient))}
    CLIENT.AUDIT.clear();CLIENT.AUDIT_PATH=out/'normalization_audit.json';CLIENT.AUDIT_IDENTITY={}
    write(CLIENT.AUDIT_PATH,[])
    shared_calls=[]
    for current in clients.values():
        current.records=shared_calls
    client=None
    def audit_context():
        call=client.records[-1]
        return {k:call[k] for k in ('group','scenario','trace','decision_period','event','stage','attempt')}
    CLIENT.AUDIT_CONTEXT=audit_context
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
            identity=dict(group=self.group,scenario=self.scenario,trace=self.trace)
            CLIENT.AUDIT_IDENTITY=identity.copy()
            if self.group=='happo':
                self.event_controller=CONTROL.V1Controller('happo',client,[],None,identity)
            else:
                self.event_controller=CONTROL.FeedbackController(self.group,client,identity)
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
                    happo_order=proposed[node],actual_order=actual[node],chosen=self.event_controller.chosen,
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
        client=clients[group]
        assert contracts(opts.input_file,opts.operator_library,opts.training_directory)==contract,'Frozen contracts changed before method'
        args=argparse.Namespace(**config);args.model_dir=str(model_dir)
        envs=Controller(args)
        runner=CRunner(dict(all_args=args,envs=envs,eval_envs=envs,num_agents=3,device=torch.device('cpu'),run_dir=out/group))
        before=model_hash(runner.policy)
        assert before==contract['expected_parameter_sha256']
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
    assert len(episodes)==24 and len(rows)==14400
    for trace in range(4):
        matched={group:[r for r in scores if r['group']==group and r['trace']==trace and r.get('generation_event')]
                 for group in METHODS[1:]}
        reference=[r['decision_period'] for r in matched['online_feedback']]
        for events in matched.values():
            assert [r['decision_period'] for r in events]==reference
            assert len(events)<=4 and all(len(r['candidates'])==4 and len(r['search_revision_feedback'])==4 for r in events)
        for group in METHODS:
            episode=next(e for e in episodes if e['group']==group and e['scenario']=='shock' and e['trace']==trace)
            assert episode['episode_http']<=16
    for scenario in ('base','shock'):
        for trace in range(4):
            end=201 if scenario=='base' else data['events'][trace]['start_index']+3
            reference=[(r['cost'],r['actual_order']) for r in rows if r['group']=='happo' and r['scenario']==scenario and r['trace']==trace and r['period']<end]
            for group in METHODS[1:]:
                assert reference==[(r['cost'],r['actual_order']) for r in rows if r['group']==group and r['scenario']==scenario and r['trace']==trace and r['period']<end]
    assert source_hashes()==contract['source_sha256'],'Frozen source changed during evaluation'
    assert digest(opts.input_file)==contract['input_sha256'] and digest(opts.operator_library)==contract['library_sha256']
    assert contracts(opts.input_file,opts.operator_library,opts.training_directory)==contract,'Frozen model or metadata changed'
    write(out/'completed.json',dict(episodes=len(episodes),rows=len(rows),training_updates=0,parameter_checks=checks,
        calls=len(shared_calls),runtime_failures=failures,wall_seconds=time.perf_counter()-started,
        development_only=True,causal_audit='Public whitelist; episode reset; synthetic-only forecast; no review in prompts'))
    CLIENT.AUDIT_CONTEXT=None;CLIENT.AUDIT_PATH=None
    print('CASE_ONLY_COMPLETED',flush=True)


if __name__=='__main__':
    main()
