"""Paired frozen Poisson HAPPO and full six-rule Sundial controller."""
import argparse
import copy
import csv
import gzip
import hashlib
import importlib.util
import inspect
import json
import os
import sys
import time
import traceback
import types
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
OUT=ROOT/'results/poisson_full_mechanism/v1'
TRAIN=ROOT/'results/poisson_optimality/formal_v1'

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value
    spec.loader.exec_module(value)
    return value

ref=module('poisson_pair_frozen_loader',ROOT/'experiments/poisson_baseline_comparison/compare.py')
locked=module('poisson_pair_six_rule_controller',ROOT/'experiments/sundial_six_rules/runner.py')
core,original,predictor=locked.core,locked.original,locked.predictor
read,write,sha=ref.read,ref.write,ref.sha

def verify():
    ref.verify()
    registration=read(OUT/'registration.json')
    for p,h in registration['files'].items():
        assert sha(ROOT/p)==h,p
    return registration

def system(lead):
    value=core.SYSTEM
    before='All shipments enter a 4-period pipeline.'
    assert value.count(before)==1
    value=value.replace(before,f'All shipments enter a {lead}-period pipeline.')
    before='Primary cost=sum of inventory+backlog at ALL 3 nodes, coefficients all1.'
    assert value.count(before)==1
    value=value.replace(before,'Primary cost=sum of inventory at ALL 3 nodes plus backlog at node0 ONLY; holding coefficients [1,1,1], backlog coefficients [1,0,0].')
    return value+'\nActual forecast provider is frozen response-adapted Sundial, not Merton. Synthetic forecast samples retain the original 0..20 bound; physical Poisson demand can exceed20. No future event magnitude or ending is available. Initial inventory and pipeline are zero.'

def reports_class():
    base=core.DemandReports
    source=inspect.getsource(base)
    assert source.count('not 0 <= value <= 20')==1
    source=source.replace('not 0 <= value <= 20','not 0 <= value')
    namespace=dict(sys.modules[base.__module__].__dict__)
    exec(compile(source,str(HERE/'runner.py'),'exec'),namespace)
    return namespace['DemandReports']

class FixtureClient:
    def __init__(self): self.records=[];self.episode_http=0
    def reset_episode(self): self.episode_http=0
    def generate(self,context,count,identity,stage):
        self.records.append(dict(**identity,stage=stage,fixture=True))
        values=[]
        for i in range(count):
            rule={'explanation':'Synthetic interface fixture, not performance evidence',
                  'rules':[{'when':'agent == 0 and growth > 1.1','delta':str(i+1)},
                           {'when':'True','delta':'0'}]}
            values.append(dict(id=f"fixture_{identity['event']}_{stage}_{i}",rule=rule,compiled=core.compile_rule(rule)))
        return values

class ActualClient(core.Client):
    def generate(self,context,count,identity,stage):
        context=copy.deepcopy(context)
        if 'forecast_protocol' in context:
            context['forecast_protocol']='6 frozen response-Sundial synthetic paths bounded0..20; search3/review3,horizon20; correction first5. Physical Poisson demand may exceed20.'
        value=super().generate(context,count,identity,stage)
        if not value: raise RuntimeError('No valid real API candidate; preserve failed/partial records')
        return value

def install_clone(env_class):
    def clone(state,history,forecast):
        env=object.__new__(env_class)
        for k,v in state.items():setattr(env,k,copy.deepcopy(v))
        env.train=False
        env.eval_index=1
        env.record_act_sta=[[],[],[]]
        env.demand_list=list(history)+list(forecast)
        env.checked_steps=0
        env.raw_cost_sum=0
        env.order_cap_hits=0
        assert not hasattr(env,'eval_data')
        return env
    # The decorated scorer's underlying namespace owns clone(), not torch's wrapper.
    inspect.unwrap(original.score).__globals__['clone']=clone
    core.clone=clone
    return clone

def dependency_files():
    paths=set()
    for obj in list(sys.modules.values()):
        p=getattr(obj,'__file__',None)
        if p:
            p=Path(p).resolve()
            if p.is_file() and p.suffix=='.py' and ROOT in p.parents:paths.add(p)
    for relative in ('experiments/poisson_full_mechanism','experiments/sundial_change_response',
                     'experiments/sundial_multiscale_cost','experiments/sundial_adapter_development',
                     'experiments/sundial_closed_loop_development','experiments/timesfm_path_development'):
        paths.update((ROOT/relative).glob('*.py'))
    paths.add(predictor.ADAPTER)
    return paths

def execute(lead,seed,fixture=False):
    import torch
    torch.set_num_threads(1)
    verify()
    directory=OUT/('fixtures' if fixture else 'runs')/f'L{lead}_seed{seed}'
    directory.mkdir(parents=True,exist_ok=False)
    start=time.time()
    try:
        wrappers,stream=ref.install(lead,directory/'unused_training_demands.jsonl')
        Env=wrappers.Env
        clone=install_clone(Env)
        Reports=reports_class()
        policies,args=ref.load_policy(lead,seed)
        before=ref.parameter_sha(policies)
        forecast_before=predictor.parameter_hash()
        torch.set_num_threads(1)
        write(directory/'protocol.json',dict(lead=lead,seed=seed,fixture=fixture,system=system(lead),
            h=[1,1,1],b=[1,0,0],model_parameter_sha256=before,
            forecast_parameter_sha256=forecast_before,adapter_sha256=sha(predictor.ADAPTER),
            actor_dim=lead+3,critic_dim=3*(lead+3),forecast_cap=20,physical_demand_unbounded=True))
        client=FixtureClient() if fixture else ActualClient(directory,system(lead),'deepseek-flash')
        data=read(OUT/'inputs.json')
        indices=range(1) if fixture else range(3)
        actors=[policy.act for policy in policies]
        # Six-rule bootstrap reuses this frozen Sundial controller factory.
        factory=locked.locked.locked.adapter.factory
        records,scores,report_log,information=[],[],[],[]
        fields='group scenario trace period node demand cost inventory backlog pipeline policy_order actual_order notification_period'.split()
        with gzip.open(directory/'periods.csv.gz','wt',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields)
            writer.writeheader()
            for group in ('happo','full_sundial'):
                for scenario in ('base','shock'):
                    for index in indices:
                        env=Env()
                        env.eval_data=[data[scenario][index]]
                        env.n_eval=1;env.eval_index=0
                        obs=env.reset(train=False)
                        reports=Reports(3)
                        history,orders=[],[]
                        rnn=[np.zeros((1,args.recurrent_N,args.hidden_size),dtype=np.float32) for _ in range(3)]
                        identity=dict(group=group,scenario=scenario,trace=index,lead=lead,seed=seed)
                        if group=='happo':controller=original.EventController('happo',None,[],None,identity)
                        else:controller=factory(original,locked.guard.adapter,predictor,locked.paths,seed,lead)(
                            'adapted_sundial',client,[],None,identity)
                        cost=0;chosen_count=0
                        for t in range(200):
                            proposed=[]
                            with torch.no_grad():
                                for i,policy in enumerate(policies):
                                    a,state=policy.act(np.asarray(obs[i])[None,:],rnn[i],np.ones((1,1),dtype=np.float32),None,deterministic=True)
                                    proposed.append(int(a.item()));rnn[i]=state.detach().cpu().numpy().copy()
                            public=reports.public_state()
                            assert public['observed_periods']==t and public['delivered_through_period']==t//3*3
                            notify=scenario=='shock' and t==data['events'][index]['start_index']+2
                            actual,record=controller.decide(env,history,orders,proposed,rnn,actors,reports,notify)
                            if record:
                                scores.append(record)
                                write(directory/'scores.json',scores)
                            information.append(dict(**identity,decision_period=t+1,delivered_through=public['delivered_through_period'],report_age=reports.age))
                            state=original.snapshot(env,history)
                            obs,reward,_,_=env.step(actual,one_hot=False)
                            demand=int(env.get_demand()[0])
                            observed=clone(state,history,[demand]);observed.step(actual,one_hot=False)
                            assert np.array_equal(observed.inventory,env.inventory) and np.array_equal(observed.backlog,env.backlog) and np.array_equal(observed.order,env.order)
                            history.append(demand);orders.append(actual.copy())
                            delivered=reports.observe(demand,t+1)
                            if delivered:report_log.append(dict(**identity,**delivered))
                            chosen_count+=int(controller.chosen!='zero')
                            for i in range(3):
                                value=int(env.inventory[i])+(int(env.backlog[i]) if i==0 else 0)
                                assert value==-float(reward[i][0])
                                cost+=value
                                writer.writerow(dict(group=group,scenario=scenario,trace=index,period=t+1,node=i,demand=demand,
                                    cost=value,inventory=int(env.inventory[i]),backlog=int(env.backlog[i]),pipeline=json.dumps(list(map(int,env.order[i])),separators=(',',':')),
                                    policy_order=proposed[i],actual_order=actual[i],notification_period='' if controller.notification is None else controller.notification+1))
                            if t==199:
                                assert group=='happo' or client.episode_http<=16
                                records.append(dict(**identity,cost=cost/600,generation_events=controller.events,
                                    http=0 if group=='happo' else client.episode_http,chosen_periods=chosen_count))
                                write(directory/'episodes.json',records)
                                write(directory/'information.json',information)
                                write(directory/'reports.json',report_log)
                                if fixture:write(directory/'fixture_calls.json',client.records)
                                print('EPISODE',records[-1],flush=True)
        assert ref.parameter_sha(policies)==before
        forecast_after=predictor.parameter_hash()
        assert forecast_after==forecast_before
        stream.close()
        verify()
        write(directory/'simulation_completed.json',dict(episodes=len(records),rows=len(records)*600,
             fixture=fixture,http=0 if fixture else len(client.records),semantic=0 if fixture else sum(r['attempt']==1 for r in client.records),
             actor_unchanged=True,forecast_unchanged=True,parameter_sha256=before,seconds=time.time()-start))
        import subprocess
        subprocess.run([sys.executable,str(HERE/'audit.py'),str(directory)],cwd=ROOT,check=True)
        write(directory/'completed.json',read(directory/'simulation_completed.json'))
    except BaseException:
        write(directory/'failed.json',dict(traceback=traceback.format_exc(),fixture=fixture,preserved=True))
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--lead',type=int,choices=(2,4),required=True)
    p.add_argument('--seed',type=int,choices=range(11,16),required=True)
    p.add_argument('--fixture',action='store_true')
    a=p.parse_args();execute(a.lead,a.seed,a.fixture)
