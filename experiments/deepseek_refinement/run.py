"""Small bounded DeepSeek feedback experiment; original HAPPO stays frozen."""
import argparse
import copy
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import urllib.request
import urllib.error
from shadow import features, corrected, snapshot, clone, forecasts, score, select, compile_rule

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT/'external/liu-inventory'
TRAINING = ROOT/'results/learning_curve/curve_seed11_until_stable_v1'
SYSTEM = '''Design bounded correction rules for a frozen HAPPO serial inventory policy.
Nodes: 0 disaster dispensing point, 1 regional warehouse, 2 upstream supply center.
Unchanged simulator: each period external demand plus node0 backlog is served from its inventory and pipeline arrival.
Node1 demand is node0 CURRENT order plus node1 backlog; node2 demand is node1 CURRENT order plus node2 backlog.
Unfilled demand becomes backlog. Next shipments to lower nodes are min(the next node demand including backlog, that next node inventory+arrival BEFORE its update). Node2 receives its own order without supplier constraint. All shipments enter a 4-period pipeline. Orders 0..20.
Primary cost=sum of inventory+backlog at ALL 3 nodes, coefficients all1. Also avoid increasing downstream backlog. An upstream reduction can starve downstream after delay; downstream extra orders can create upstream backlog. Observe all nodes and pipelines together.
You are notified a demand emergency HAS occurred. Future demand, duration and magnitude are unknown. You only see past demand and current state. Do not infer knowledge of the event end. HAPPO does not train.
Return JSON {"candidates":[{"explanation":"...","rules":[{"when":"expression","delta":"expression"}]}]}.
User specifies candidate count (3 initial, 1 refinement). Each rule set contains1..4 ordered first-match rules evaluated separately for each node.
Expression features ONLY: agent, inventory, backlog, pipeline=sum of known in-transit, arrival=next known arrival, incoming=last observed local demand, recent=last5 external mean, baseline=preceding20 external mean, growth=recent/baseline, happo=current proposed order.
Expressions <=300 characters may use numbers, + - * /, comparisons, and/or/not, conditional expressions, min/max2..6args, abs1arg. No other names, code, attributes, imports or containers.
Delta clipped[-6,6], rounded, added to HAPPO order and clipped0..20. Prefer small coordinated corrections and pipeline-aware relaxation. Rules run on fresh causal state for each period. Zero correction is valid.
For feedback, scores are uncertain causal forecast rollouts, not actual future results. Improve both cost and downstream service; do not exploit sample noise. Explain mechanics briefly, no markdown.'''


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name', default='flash_refinement_2cases_v1')
    parser.add_argument('--cases',type=int,default=2,choices=(2,4))
    parser.add_argument('--demand-seed',type=int,default=20261011)
    parser.add_argument('--event-seed',type=int,default=20261012)
    parser.add_argument('--correction-periods',type=int,default=20,choices=(5,20))
    parser.add_argument('--refinement-schedule',default='immediate',choices=('immediate','observed'))
    opts = parser.parse_args()
    run_started=time.perf_counter()
    if not opts.run_name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in opts.run_name):
        parser.error('invalid run name')
    out = ROOT/'results/deepseek_refinement'/opts.run_name
    if out.exists(): parser.error('refuse overwrite')
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key: parser.error('API key missing')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=UPSTREAM, text=True).strip()
    assert revision == 'a7e5a3e83e21565a5799483bc534e39635ec65dd'
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=UPSTREAM, text=True).strip()
    old_calls = 0
    for p in (ROOT/'results/deepseek_refinement').glob('*/calls.json'):
        old_calls += len(json.loads(p.read_text(encoding='utf-8')))
    if old_calls+12 > 120: parser.error('series API limit reached')
    out.mkdir(parents=True)
    write(out/'protocol.json', {'system': SYSTEM, 'document': 'docs/2026-10-03-llm-refinement-protocol.md',
                               'max_calls': 12, 'series_calls_before': old_calls, 'model': 'deepseek-flash',
                               'options':vars(opts)})
    sys.path.insert(0, str(UPSTREAM)); os.chdir(UPSTREAM)
    import numpy as np
    import torch
    from envs import generator
    from envs.env_wrappers import DummyVecEnv
    from runners.separated.runner import CRunner
    torch.set_num_threads(1); torch.manual_seed(11); np.random.seed(opts.demand_seed)
    base = [generator.merton(200, 20).demand_list for _ in range(opts.cases)]
    rng = random.Random(opts.event_seed)
    events = [dict(start_index=rng.randint(60, 100), duration=rng.randint(20, 40)) for _ in base]
    shock = [[min(20, math.ceil(1.5*d)) if e['start_index'] <= i < e['start_index']+e['duration'] else d
              for i, d in enumerate(t)] for t, e in zip(base, events)]
    write(out/'demands.json', {'demand_seed': opts.demand_seed, 'event_seed': opts.event_seed, 'events': events, 'base': base, 'shock': shock})
    calls = []; scores = []; rows = []; episodes = []; initial = {}; checks = {}; failures = []; branch_audits=[]; feedback_times=[]
    config = json.loads((TRAINING/'config.json').read_text())['config']
    done = json.loads((TRAINING/'completed.json').read_text())
    model_dir = Path(done['final_model_directory']).parent/'models'
    audit = json.loads((TRAINING/'completion_audit.json').read_text())

    def model_hash(policies):
        digest = hashlib.sha256()
        for p in policies:
            for net in (p.actor, p.critic):
                for n, t in net.state_dict().items():
                    digest.update(n.encode()); digest.update(t.detach().cpu().numpy().tobytes())
        return digest.hexdigest()

    def generate(context, count, trace, round_id):
        assert len(calls) < 12
        body = dict(model='deepseek-flash', messages=[dict(role='system', content=SYSTEM),
                    dict(role='user', content=json.dumps(dict(context, candidate_count=count)))],
                    response_format={'type':'json_object'}, thinking={'type':'disabled'}, temperature=.2, max_tokens=3000)
        record = dict(index=len(calls), trace=trace, round=round_id, request=body, status='started')
        calls.append(record); write(out/'calls.json', calls)
        start = time.perf_counter(); result = []
        try:
            req = urllib.request.Request('https://api.deepseek.com/chat/completions', data=json.dumps(body).encode(),
                    headers={'Authorization':'Bearer '+key, 'Content-Type':'application/json'})
            with urllib.request.urlopen(req, timeout=30) as stream:
                response = json.load(stream)
            record['response'] = response
            choice = response['choices'][0]
            if choice['finish_reason'] != 'stop': raise ValueError('incomplete output')
            values = json.loads(choice['message']['content'])['candidates']
            if len(values) != count: raise ValueError('wrong candidate count')
            for i, value in enumerate(values):
                try:
                    result.append(dict(id=f'llm_r{round_id}_{i}', compiled=compile_rule(value), rule=value))
                except Exception as exc:
                    record.setdefault('invalid_candidates', []).append(dict(index=i, failure=type(exc).__name__))
            record['candidates'] = values; record['status'] = 'valid' if result else 'failed'
        except urllib.error.HTTPError as exc:
            record['status']='failed'; record['failure']='HTTP_'+str(exc.code)
        except Exception as exc:
            record['status']='failed'; record['failure']=type(exc).__name__
        record['seconds']=time.perf_counter()-start; write(out/'calls.json', calls)
        print('API', trace, round_id, record['status'], round(record['seconds'],2), flush=True)
        return result

    class Controller(DummyVecEnv):
        def reset(self):
            self.trace = self.env_list[0].eval_index
            self.history=[]; self.orders=[]; self.candidates=[dict(id='zero')]; self.chosen='zero'; self.context=None
            self.notification=None; self.recurrent=[None]*3; self.episode_rows=[]
            self.audit_start=None
            return super().reset()

        def step(self, actions):
            env=self.env_list[0]; period=env.step_num
            proposed=[int(np.argmax(a)) for a in actions[0]]
            notify = self.scenario=='shock' and period==events[self.trace]['start_index']+2
            if notify:
                self.notification=period+1
                if self.group=='happo':
                    self.audit_start=dict(state=snapshot(env,self.history),history=self.history.copy(),orders=copy.deepcopy(self.orders),
                                          proposed=proposed.copy(),recurrent=copy.deepcopy(self.recurrent))
                fs=features(env,self.history,self.orders,proposed)
                self.context=dict(observed_periods=period, observed_last25_demands=self.history[-25:], nodes=fs,
                                  known_pipeline=[list(map(int,p)) for p in env.order],
                                  last5_orders=self.orders[-5:], notification='emergency has occurred')
                if self.group=='manual_screen': self.candidates.append(dict(id='manual'))
                if self.group=='llm_single':
                    generated=generate(self.context,3,self.trace,0)
                    initial[self.trace]=dict(context=copy.deepcopy(self.context), generated=generated)
                    # Preserve exactly candidate0; invalid0 is a fallback, not favourable replacement.
                    self.candidates += [c for c in generated if c['id']=='llm_r0_0']
                if self.group=='llm_iterative':
                    assert initial[self.trace]['context']==self.context
                    self.candidates += initial[self.trace]['generated']
                print('NOTIFIED',self.group,self.trace,period+1,flush=True)
            if self.notification is not None and self.group!='happo' and (period-(self.notification-1))%5==0:
                state=snapshot(env,self.history); paths=forecasts(self.history,self.trace,period)
                # Zero shadow first step must exactly equal original transition on identical synthetic demand.
                branch=clone(state,self.history,paths[0][0]); branch.step(proposed,one_hot=False)
                verify=clone(state,self.history,paths[0][0]); verify.step(corrected(dict(id='zero'),verify,self.history,self.orders,proposed),one_hot=False)
                assert branch.inventory==verify.inventory and branch.backlog==verify.backlog and branch.order==verify.order
                if self.group=='llm_iterative':
                    elapsed=period-(self.notification-1)
                    rounds=(1,2) if notify and opts.refinement_schedule=='immediate' else (
                        (elapsed//10,) if opts.refinement_schedule=='observed' and elapsed in (10,20) else ())
                    for round_id in rounds:
                        feedback_started=time.perf_counter()
                        feedback=[score(c,state,self.history,self.orders,proposed,self.recurrent,self.actors,paths[0],opts.correction_periods) for c in self.candidates]
                        feedback_times.append(dict(trace=self.trace,round=round_id,seconds=time.perf_counter()-feedback_started))
                        context=dict(self.context, forecast_method='last5 mean + sampled last20 residuals, horizon20',
                                     search_feedback=feedback,
                                     previous_candidates=[{'id':c['id'],'rule':c.get('rule')} for c in self.candidates])
                        if opts.refinement_schedule=='observed':
                            context.update(observed_periods=period,observed_last25_demands=self.history[-25:],
                                nodes=features(env,self.history,self.orders,proposed),known_pipeline=[list(map(int,p)) for p in env.order],
                                last5_orders=self.orders[-5:],
                                observed_cost_last10=[sum(r['cost'] for r in self.episode_rows if r['node']==i and r['period']>period-10)/10 for i in range(3)],
                                invalid_generation_records=[{'round':c['round'],'invalid_candidates':c.get('invalid_candidates',[]),'failure':c.get('failure')}
                                    for c in calls if c['trace']==self.trace and c['status']!='valid'])
                        if opts.correction_periods==5:
                            context['control_horizon']='Candidate applied first5 periods; remaining forecast horizon follows frozen HAPPO without correction. Real controller reselects every5 periods.'
                        self.candidates += generate(context,1,self.trace,round_id)
                self.chosen, result=select(self.candidates,state,self.history,self.orders,proposed,self.recurrent,self.actors,paths,opts.correction_periods)
                scores.append(dict(group=self.group,trace=self.trace,period=period+1, forecasts=paths, **result))
                write(out/'scores.json',scores)
                print('SELECT',self.group,self.trace,period+1,self.chosen,round(result['seconds'],2),flush=True)
            rule=next(c for c in self.candidates if c['id']==self.chosen)
            try: actual=corrected(rule,env,self.history,self.orders,proposed)
            except Exception as exc:
                failures.append(dict(group=self.group,trace=self.trace,period=period+1,failure=type(exc).__name__))
                actual=proposed.copy(); self.chosen='zero'
            causal_state=snapshot(env,self.history)
            output=super().step([[np.eye(21)[a] for a in actual]])
            demand=int(env.get_demand()[0]); self.history.append(demand); self.orders.append(actual.copy())
            # Verification AFTER observing demand; never used for candidate evaluation or choice.
            observed_clone=clone(causal_state,self.history[:-1],[demand]);observed_clone.step(actual,one_hot=False)
            assert observed_clone.inventory==env.inventory and observed_clone.backlog==env.backlog and observed_clone.order==env.order
            for node in range(3):
                row=dict(group=self.group,scenario=self.scenario,trace=self.trace,period=env.step_num,node=node,
                         demand=demand,cost=-float(output[1][0,node,0]),inventory=int(env.inventory[node]),backlog=int(env.backlog[node]),
                         happo_order=proposed[node],actual_order=actual[node],chosen=self.chosen,notification_period=self.notification)
                rows.append(row);self.episode_rows.append(row)
            if env.step_num==200:
                if self.audit_start is not None:
                    a=self.audit_start;p=a['state']['step_num'];path=self.history[p:p+20]
                    predicted=score(dict(id='zero'),a['state'],a['history'],a['orders'],a['proposed'],a['recurrent'],self.actors,[path])
                    rr=[r for r in self.episode_rows if p<r['period']<=p+len(path)]
                    observed_cost=sum(r['cost'] for r in rr);observed_backlog=sum(r['backlog'] for r in rr if r['node']==0)
                    assert predicted['valid'] and predicted['cost']==observed_cost and predicted['downstream']==observed_backlog
                    branch_audits.append(dict(trace=self.trace,period=p+1,shadow_cost=predicted['cost'],observed_cost=observed_cost,
                                             shadow_backlog=predicted['downstream'],observed_backlog=observed_backlog,
                                             note='After-episode verification on observed demand, never used by selector'))
                    write(out/'branch_audits.json',branch_audits)
                episodes.append(dict(group=self.group,scenario=self.scenario,trace=self.trace,notification=self.notification,
                            cost=float(np.mean([r['cost'] for r in self.episode_rows])),
                            downstream_backlog=float(np.mean([r['backlog'] for r in self.episode_rows if r['node']==0])) ))
                write(out/'episodes.json',episodes)
                with (out/'periods.csv').open('w',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
                print('EPISODE',episodes[-1],flush=True)
            return output

    for group in ('happo','manual_screen','llm_single','llm_iterative'):
        args=argparse.Namespace(**config);args.model_dir=str(model_dir)
        envs=Controller(args)
        runner=CRunner(dict(all_args=args,envs=envs,eval_envs=envs,num_agents=3,device=torch.device('cpu'),run_dir=out/group))
        before=model_hash(runner.policy);assert before==audit['model_matches']['official_best']['sha256']
        envs.actors=[]
        for i,p in enumerate(runner.policy):
            original=p.act;envs.actors.append(original)
            def capture(*a,_original=original,_i=i,**kw):
                result=_original(*a,**kw)
                envs.recurrent[_i]=result[1].detach().cpu().numpy().copy()
                return result
            p.act=capture
        for scenario,demands in (('base',base),('shock',shock)):
            env=envs.env_list[0];env.eval_data=demands;env.n_eval=opts.cases;env.eval_index=0;env.record_act_sta=[[],[],[]]
            envs.group=group;envs.scenario=scenario
            reward,_=runner.eval()
            es=[e for e in episodes if e['group']==group and e['scenario']==scenario]
            assert math.isclose(-float(reward),np.mean([e['cost'] for e in es]),abs_tol=1e-9)
        after=model_hash(runner.policy);assert before==after
        checks[group]=dict(before=before,after=after,unchanged=True)
        runner.writter.close();envs.close()
    assert len(episodes)==8*opts.cases and len(rows)==4800*opts.cases
    for scenario in ('base','shock'):
        for trace in range(opts.cases):
            end=201 if scenario=='base' else events[trace]['start_index']+3
            reference=[(r['cost'],r['actual_order']) for r in rows if r['group']=='happo' and r['scenario']==scenario and r['trace']==trace and r['period']<end]
            for group in ('manual_screen','llm_single','llm_iterative'):
                assert reference==[(r['cost'],r['actual_order']) for r in rows if r['group']==group and r['scenario']==scenario and r['trace']==trace and r['period']<end]
    write(out/'runtime_failures.json',failures)
    write(out/'completed.json',dict(episodes=len(episodes),rows=len(rows),training_updates=0,parameter_checks=checks,calls=len(calls),
                    upstream_revision=revision,causal_audit='explicit whitelist; synthetic-only branch futures; paired initial contexts; unchanged pre-notification actions',
                    runtime_failures=failures,branch_audits=branch_audits,feedback_times=feedback_times,
                    wall_seconds=time.perf_counter()-run_started))
    print('REFINEMENT_COMPLETED',flush=True)


if __name__=='__main__': main()
