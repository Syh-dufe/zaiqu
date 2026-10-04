"""Complete and partial development summaries; all model/trace results retained."""
import argparse
import csv
from pathlib import Path
import statistics
from run import METHODS,read,write


def mean(values):
    return statistics.mean(values) if values else None


def analyze(out,require_complete=False):
    fitness=[];calls=[];selections=[];failures=[];audits=[];metrics=[]
    changed_orders=0;total_orders=0
    for seed in (11,12):
        folder=out/f'seed{seed}'
        if not folder.exists():
            failures.append(dict(seed=seed,status='not_started'));continue
        episodes=read(folder/'episodes.json') if (folder/'episodes.json').exists() else []
        scores=read(folder/'scores.json') if (folder/'scores.json').exists() else []
        records=read(folder/'calls.json') if (folder/'calls.json').exists() else []
        for episode in episodes:
            fitness.append(dict(seed=seed,**episode))
        calls.extend(dict(seed=seed,**r) for r in records)
        selections.extend(dict(seed=seed,**r) for r in scores)
        if (folder/'failed.json').exists():
            failures.append(dict(seed=seed,**read(folder/'failed.json')))
        if (folder/'runtime_failures.json').exists():
            failures.extend(dict(seed=seed,**r) for r in read(folder/'runtime_failures.json'))
        if (folder/'periods.csv').exists():
            with (folder/'periods.csv').open(encoding='utf-8',newline='') as stream:
                rows=list(csv.DictReader(stream))
            changed_orders+=sum(r['actual_order']!=r['happo_order'] for r in rows)
            total_orders+=len(rows)
            if any(float(r['cost'])!=float(r['inventory'])+float(r['backlog']) for r in rows):
                raise ValueError('Original unit holding/backlog cost mismatch')
            for episode in episodes:
                local=[r for r in rows if r['group']==episode['group'] and r['scenario']==episode['scenario'] and int(r['trace'])==episode['trace']]
                if len(local)!=600 or {(int(r['period']),int(r['node'])) for r in local}!={(period,node) for period in range(1,201) for node in range(3)}:
                    raise ValueError('Completed episode must have600 unique period/node rows')
                cost=mean([float(r['cost']) for r in local]);backlog=mean([float(r['backlog']) for r in local if r['node']=='0'])
                if cost is None or abs(cost-episode['cost'])>1e-9 or abs(backlog-episode['downstream_backlog'])>1e-9:
                    raise ValueError('Raw cost/backlog reconstruction differs')
                audits.append(dict(seed=seed,group=episode['group'],scenario=episode['scenario'],trace=episode['trace'],cost_reconstructed=True))
                downstream=[r for r in local if r['node']=='0'];notification=episode['notification_period']
                windows={}
                if notification:
                    for horizon in (10,20):
                        windows[str(horizon)]=sum(float(r['backlog']) for r in downstream if notification<=int(r['period'])<notification+horizon)
                event=read(out/'inputs.json')['events'][episode['trace']]
                after=[r for r in downstream if int(r['period'])>=event['start_index']+1]
                end=event['start_index']+event['duration']+1
                recovery=None
                # Registered descriptive recovery: first5 consecutive zero-backlog periods after shock end.
                for i in range(len(downstream)-4):
                    if int(downstream[i]['period'])>=end and all(float(r['backlog'])==0 for r in downstream[i:i+5]):
                        recovery=int(downstream[i]['period'])-end;break
                metrics.append(dict(seed=seed,group=episode['group'],scenario=episode['scenario'],trace=episode['trace'],
                    notification_window_backlog=windows,peak_backlog=max(float(r['backlog']) for r in after),
                    recovery_periods=recovery,recovery_censored=recovery is None,tail_inventory=[int(r['inventory']) for r in local if int(r['period'])==200]))
    paired=[];per_model=[]
    for seed in (11,12):
        for group in METHODS[1:]:
            local=[]
            for trace in range(4):
                baseline=next((e for e in fitness if e['seed']==seed and e['trace']==trace and e['scenario']=='shock' and e['group']=='happo'),None)
                candidate=next((e for e in fitness if e['seed']==seed and e['trace']==trace and e['scenario']=='shock' and e['group']==group),None)
                if baseline and candidate:
                    delta=dict(seed=seed,trace=trace,group=group,cost_delta=candidate['cost']-baseline['cost'],
                        backlog_delta=candidate['downstream_backlog']-baseline['downstream_backlog'])
                    paired.append(delta);local.append(delta)
            per_model.append(dict(seed=seed,group=group,pairs=len(local),mean_cost_delta=mean([r['cost_delta'] for r in local]),
                mean_backlog_delta=mean([r['backlog_delta'] for r in local])))
    bad=[r for r in paired if r['cost_delta']>0 or r['backlog_delta']>0]
    generation=[r for r in selections if r.get('generation_event')]
    comparisons=[]
    import numpy as np
    # Crossed resampling is descriptive for only2 models and4 development traces.
    for reference,method in [('happo',g) for g in METHODS[1:]]+[('llm_library','online_feedback'),('random_screen','online_feedback'),('online_once','online_feedback')]:
        delta=[]
        for seed in (11,12):
            model=[]
            for trace in range(4):
                pair=[next((e for e in fitness if e['seed']==seed and e['trace']==trace and e['scenario']=='shock' and e['group']==g),None) for g in (reference,method)]
                if all(pair):
                    model.append([pair[1]['cost']-pair[0]['cost'],pair[1]['downstream_backlog']-pair[0]['downstream_backlog']])
            delta.append(model)
        if all(len(v)==4 for v in delta):
            values=np.asarray(delta);rng=np.random.default_rng(20270804)
            models=rng.integers(0,2,(10000,2));traces=rng.integers(0,4,(10000,4))
            draws=values[models[:,:,None],traces[:,None,:]].mean(axis=(1,2))
            comparisons.append(dict(reference=reference,method=method,mean_delta=values.mean(axis=(0,1)).tolist(),
                descriptive_crossed_ci95=np.quantile(draws,[.025,.975],axis=0).tolist()))
    usage={}
    for record in calls:
        for key,value in (record.get('usage') or {}).items():
            if isinstance(value,(int,float)):
                usage[key]=usage.get(key,0)+value
    summary=dict(development_only=True,claim_limit='Small development batch; no independent efficacy claim or LLM attribution vs random without support',
        episodes_observed=len(fitness),expected_episodes=80,fitness=fitness,paired_deltas=paired,per_model=per_model,comparisons=comparisons,
        all_unfavorable_pairs=bad,failures=failures,raw_metric_audits=audits,episode_metrics=metrics,
        api_requests=len(calls),api_failures=sum(r['status']!='valid' for r in calls),api_seconds=sum(r.get('seconds',0) for r in calls),usage=usage,
        screening_seconds=sum(r.get('seconds',0)+r.get('revision_scoring_seconds',0) for r in selections),
        selection_events=len(selections),generation_events=len(generation),
        accepted_selections=sum(r.get('chosen')!='zero' for r in selections),
        changed_node_orders=changed_orders,total_node_orders=total_orders,
        recovery_definition='First5 consecutive zero downstream backlog periods after actual shock end; posthoc descriptive only; censored if absent')
    inputs=read(out/'inputs.json')
    summary['realized_demand_shocks']=[dict(trace=i,intensity=e['intensity'],
        base_total=sum(inputs['base'][i][e['start_index']:e['start_index']+e['duration']]),
        shock_total=sum(inputs['shock'][i][e['start_index']:e['start_index']+e['duration']]),
        clipped_periods=sum(e['intensity']*v>20 for v in inputs['base'][i][e['start_index']:e['start_index']+e['duration']])) for i,e in enumerate(inputs['events'])]
    if require_complete and (len(fitness)!=80 or total_orders!=48000):
        raise ValueError('Full development batch requires80 episodes and48000 node rows')
    if require_complete and {(e['seed'],e['group'],e['scenario'],e['trace']) for e in fitness}!={
        (seed,group,scenario,trace) for seed in (11,12) for group in METHODS for scenario in ('base','shock') for trace in range(4)}:
        raise ValueError('Registered crossed episode keys differ')
    write(out/'summary.json',summary)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    analyze(parser.parse_args().output.resolve())
