"""Append mixed-shock-trained HAPPO to cached common-input comparisons; no API."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/happo_matched_evaluation/appendix_v1'
OLD=ROOT/'results/joint_baseline_confirmation/confirmation_v1'
TRAIN=ROOT/'results/happo_matched_shock/formal_v2'
AUTHOR=ROOT/'external/liu-inventory'
PLAN=ROOT/'docs/superpowers/plans/2026-10-12-matched-shock-comparison.md'
TYPES=('single_surge','sustained_surge','double_surge','surge_then_drop')
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def training(s):return ROOT/f'results/learning_curve/matched_shock_seed{s}_v2'
def verify(m):
    for p,h in m['hashes'].items():assert sha(ROOT/p)==h,p
def cached(summary):
    result=[]
    for run in summary['runs']:
        folder=OLD/'runs'/run['label']; ep=read(folder/'episodes.json')
        assert sha(folder/'completed.json')==run['completed_sha256']
        sums={};counts={};seen=set()
        with (folder/'periods.csv').open(encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                key=(r['group'],r['scenario'],int(r['trace']))
                ident=key+(int(r['period']),int(r['node']))
                assert ident not in seen;seen.add(ident)
                cost=int(r['inventory'])+int(r['backlog']);assert cost==float(r['cost'])
                sums[key]=sums.get(key,0)+cost;counts[key]=counts.get(key,0)+1
        assert len(seen)==14400 and len(ep)==24
        for e in ep:
            key=(e['group'],e['scenario'],e['trace']);assert counts[key]==600
            assert math.isclose(sums[key]/600,e['cost'],abs_tol=1e-10)
            result.append(dict(seed=run['seed'],batch=run['batch'],**e))
    assert len(result)==1200
    for group in ('happo','ippo','online_feedback'):
        for scenario in ('base','shock'):
            value=np.mean([e['cost'] for e in result if e['group']==group and e['scenario']==scenario])
            assert math.isclose(value,summary['method_means'][group][scenario]['cost'],abs_tol=1e-10)
    return result
def register():
    assert not OUT.exists();assert read(TRAIN/'completed.json')['api_calls']==0
    summary=read(OLD/'summary.json');assert sha(OLD/'summary.json')==read(OLD/'completed.json')['summary_sha256']
    cache=cached(summary)
    files=[Path(__file__),PLAN,OLD/'summary.json',OLD/'completed.json',TRAIN/'manifest.json',TRAIN/'completed.json']
    files+=list(AUTHOR.rglob('*.py'))+list((AUTHOR/'test_data/test_demand_merton').glob('*.txt'))
    files+=[ROOT/'experiments/joint_baseline/frozen.py']
    for run in summary['runs']:
        files += [OLD/'runs'/run['label']/n for n in ('episodes.json','periods.csv','completed.json')]
    files+=sorted((OLD/'inputs').glob('batch*.json'));assert len(list((OLD/'inputs').glob('batch*.json')))==10
    contracts={}
    for seed in range(11,16):
        folder=training(seed);done=read(folder/'completed.json');audit=read(folder/'completion_audit.json')
        model=Path(done['final_model_directory']).parent/'models'
        assert done['best_scheduled_evaluation']['step'] in audit['model_matches']['official_best']['matching_steps']
        assert audit['evaluated_original_costs']['official_best']==done['official_best_cost']
        contracts[str(seed)]=dict(model=str(model),parameter=audit['model_matches']['official_best']['sha256'])
        files += [folder/n for n in ('config.json','completed.json','completion_audit.json')]
        files += [model/f'{kind}_agent{i}.pt' for i in range(3) for kind in ('actor','critic')]
    for p in files:
        if p.suffix=='.py':compile(p.read_bytes(),str(p),'exec')
    m=dict(hashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in set(files)},models=contracts,seeds=list(range(11,16)),episodes=400,node_periods=240000,api_calls=0,training_updates=0,scope='Supplementary comparison on previously observed test inputs',bootstrap_seed=20272013)
    verify(m);OUT.mkdir(parents=True);write(OUT/'manifest.json',m);write(OUT/'cached_episodes.json',cache)
    m['hashes'][str((OUT/'cached_episodes.json').relative_to(ROOT)).replace('\\','/')]=sha(OUT/'cached_episodes.json');write(OUT/'manifest.json',m)
    write(OUT/'preflight.json',dict(passed=True,cached_episodes_recomputed=1200,new_episodes=400,api_calls=0))
    print('REGISTERED',len(m['hashes']),flush=True)
def evaluate():
    m=read(OUT/'manifest.json');verify(m)
    with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
    write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time()))
    sys.path.insert(0,str(AUTHOR));os.chdir(AUTHOR)
    sys.path.insert(0,str(ROOT/'experiments/joint_baseline'))
    from frozen import parameter_hash
    import torch
    from envs.env_wrappers import DummyVecEnv
    from runners.separated.runner import CRunner
    torch.set_num_threads(1)
    episodes=[];checks=[];start=time.time()
    class Recorded(DummyVecEnv):
        def reset(self):
            self.trace=self.env_list[0].eval_index;self.local=[]
            return super().reset()
        def step(self,actions):
            output=super().step(actions);env=self.env_list[0];p=env.step_num
            assert int(env.get_demand()[0])==self.data[self.scenario][self.trace][p-1]
            for node in range(3):
                order=int(np.argmax(actions[0][node]));assert 0<=order<=20
                cost=int(env.inventory[node])+int(env.backlog[node]);assert cost==-float(output[1][0,node,0])
                r=dict(seed=self.seed,batch=self.batch,scenario=self.scenario,trace=self.trace,period=p,node=node,demand=int(env.get_demand()[0]),inventory=int(env.inventory[node]),backlog=int(env.backlog[node]),cost=cost,order=order)
                self.writer.writerow(r);self.local.append(r)
            if p==200:
                assert len(self.local)==600
                episodes.append(dict(seed=self.seed,batch=self.batch,scenario=self.scenario,trace=self.trace,type=self.data['events'][self.trace]['type'],cost=sum(r['cost'] for r in self.local)/600))
            return output
    try:
        for seed in m['seeds']:
            verify(m);torch.manual_seed(seed)
            cfg=read(training(seed)/'config.json')['config'];args=argparse.Namespace(**cfg);args.model_dir=m['models'][str(seed)]['model']
            folder=OUT/f'seed{seed}';folder.mkdir()
            envs=Recorded(args);envs.seed=seed
            runner=CRunner(dict(all_args=args,envs=envs,eval_envs=envs,num_agents=3,device=torch.device('cpu'),run_dir=folder))
            before=parameter_hash(runner.policy);assert before==m['models'][str(seed)]['parameter']
            fields=('seed','batch','scenario','trace','period','node','demand','inventory','backlog','cost','order')
            with (folder/'periods.csv').open('x',newline='',encoding='utf-8') as f:
                envs.writer=csv.DictWriter(f,fieldnames=fields);envs.writer.writeheader()
                for batch in range(1,11):
                    data=read(OLD/f'inputs/batch{batch:02}.json');envs.data=data;envs.batch=batch
                    for scenario in ('base','shock'):
                        envs.scenario=scenario;env=envs.env_list[0];env.eval_data=data[scenario];env.n_eval=4;env.eval_index=0;env.record_act_sta=[[],[],[]]
                        reward,_=runner.eval()
                        local=[e for e in episodes if e['seed']==seed and e['batch']==batch and e['scenario']==scenario]
                        assert len(local)==4 and math.isclose(-float(reward),np.mean([e['cost'] for e in local]),abs_tol=1e-9)
            after=parameter_hash(runner.policy);assert after==before;runner.writter.close();envs.close();verify(m)
            rows=list(csv.DictReader((folder/'periods.csv').open(encoding='utf-8')))
            keyed={(int(r['batch']),r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in rows}
            assert len(rows)==len(keyed)==48000
            for batch in range(1,11):
                data=read(OLD/f'inputs/batch{batch:02}.json')
                for trace,event in enumerate(data['events']):
                    for p in range(1,event['start_index']+1):
                        for node in range(3):
                            left=keyed[batch,'base',trace,p,node];right=keyed[batch,'shock',trace,p,node]
                            assert all(left[k]==right[k] for k in ('inventory','backlog','cost','order'))
            checks.append(dict(seed=seed,before=before,after=after,node_periods=len(rows),cost_and_prefix_checked=True))
            write(folder/'completed.json',checks[-1]);write(OUT/'episodes.json',episodes);write(OUT/'progress.json',dict(completed_seeds=[c['seed'] for c in checks],episodes=len(episodes)))
            print('SEED_COMPLETED',seed,flush=True)
        assert len(episodes)==400
        old=read(OUT/'cached_episodes.json');paired=[];comparisons={}
        for group in ('online_feedback','happo','ippo'):
            values=np.zeros((4,10,5));records=[]
            for e in episodes:
                if e['scenario']!='shock':continue
                other=next(x for x in old if x['group']==group and all(x[k]==e[k] for k in ('seed','batch','scenario','trace')))
                delta=e['cost']-other['cost'];values[TYPES.index(e['type']),e['batch']-1,e['seed']-11]=delta
                records.append(dict(**e,comparison=group,reference_cost=other['cost'],difference=delta))
            rng=np.random.default_rng(20272013);models=rng.integers(0,5,size=(20000,5));draws=np.zeros(20000)
            for a in values:
                paths=rng.integers(0,10,size=(20000,10));draws+=a[paths[:,:,None],models[:,None,:]].mean(axis=(1,2))/4
            comparisons[group]=dict(mean_difference=float(values.mean()),ci95=list(map(float,np.quantile(draws,[.025,.975]))),better=sum(r['difference']<0 for r in records),tied=sum(r['difference']==0 for r in records),worse=sum(r['difference']>0 for r in records),by_seed={str(s):float(np.mean([r['difference'] for r in records if r['seed']==s])) for s in m['seeds']},by_type={t:float(np.mean([r['difference'] for r in records if r['type']==t])) for t in TYPES})
            paired+=records
        means={g:float(np.mean([e['cost'] for e in old if e['group']==g and e['scenario']=='shock'])) for g in ('happo','ippo','online_feedback')}
        means['shock_trained_happo']=float(np.mean([e['cost'] for e in episodes if e['scenario']=='shock']))
        write(OUT/'paired_costs.json',paired);write(OUT/'model_checks.json',checks)
        write(OUT/'summary.json',dict(shock_cost_means=means,new_minus_reference=comparisons,scope=m['scope'],api_calls=0,training_updates=0,episodes=400,node_periods=240000,bootstrap='20000 crossed draws, paired model axis shared across types, ten paths per type',wall_seconds=time.time()-start))
        verify(m);write(OUT/'completed.json',dict(passed=True,episodes=400,node_periods=240000,api_calls=0,summary_sha256=sha(OUT/'summary.json')))
        print('COMPARISON_COMPLETED',json.dumps(means),flush=True)
    except Exception as exc:
        write(OUT/'failed.json',dict(type=type(exc).__name__,error=str(exc),preserved=True));raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['register','run']);a=p.parse_args()
    register() if a.action=='register' else evaluate()
