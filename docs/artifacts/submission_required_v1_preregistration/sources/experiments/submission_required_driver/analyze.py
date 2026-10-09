"""Prespecified cost-only summaries, crossed intervals and complete cases."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'submission_required'))
import numpy as np
from common import ROOT,OUTPUT,SEEDS,TYPES,read,write,digest
from reliability import summarize_resources

def crossed(values,coverage,seed=20271652):
    rng=np.random.default_rng(seed);draws=np.zeros(20000);models=rng.integers(0,5,(20000,5))
    for t in TYPES:
        a=np.array(values[t]);assert a.shape==(10,5) and np.isfinite(a).all()
        paths=rng.integers(0,10,(20000,10));draws+=a[paths[:,:,None],models[:,None,:]].mean((1,2))/4
    tail=(1-coverage)/2;low,high=np.quantile(draws,[tail,1-tail]);mean=float(np.mean(list(values.values())))
    return dict(mean=mean,low=float(low),high=float(high),coverage=coverage,replicates=20000,seed=seed,
        evidence_mean_and_upper_below_zero=bool(mean<0 and high<0),sampling='shared paired model axis; independent ten-path axes per type')

def summarize(phase,tasks,inputs):
    values={};episodes=[]
    for task in tasks:
        directory=OUTPUT/'runs'/task['label'];data=read(Path(inputs[task['input_id']]['path']))
        assert read(directory/'audit.json')['status']=='passed'
        for e in read(directory/'episodes.json'):
            row=dict(seed=task['seed'],input_id=task['input_id'],path_batch=task['path_batch'],setting=task.get('setting'),
                type=data['events'][e['trace']]['type'],**e)
            episodes.append(row);key=(task['seed'],task['input_id'],e['group'],e['scenario'],e['trace'])
            assert key not in values;values[key]=e['cost']
    methods=tasks[0]['methods'];comparisons={}
    if phase=='confirmation':
        for right in ('no_feedback','no_review','first_only','deterministic_search','happo'):
            pairs=[];matrix={t:np.zeros((10,5)) for t in TYPES}
            for task in tasks:
                seed,i=task['seed'],task['input_id'];data=read(Path(inputs[i]['path']))
                for trace,event in enumerate(data['events']):
                    delta=values[seed,i,'online_feedback','shock',trace]-values[seed,i,right,'shock',trace]
                    base=values[seed,i,'online_feedback','base',trace]-values[seed,i,right,'base',trace]
                    pairs.append(dict(seed=seed,input_id=i,type=event['type'],trace=trace,shock_cost_difference=delta,base_cost_difference=base,did=delta-base))
                    matrix[event['type']][task['path_batch']-1,SEEDS.index(seed)]=delta
            comparisons[right]=dict(bootstrap=crossed(matrix,.95 if right=='happo' else .9875),pairs=pairs,
                better=sum(x['shock_cost_difference']<0 for x in pairs),tied=sum(x['shock_cost_difference']==0 for x in pairs),
                worse=sum(x['shock_cost_difference']>0 for x in pairs),
                by_type={t:float(np.mean([x['shock_cost_difference'] for x in pairs if x['type']==t])) for t in TYPES},
                by_seed={str(s):float(np.mean([x['shock_cost_difference'] for x in pairs if x['seed']==s])) for s in SEEDS})
    settings=sorted({e.get('setting') or 'main' for e in episodes})
    means={setting:{m:{s:float(np.mean([e['cost'] for e in episodes if e['group']==m and e['scenario']==s and (e.get('setting') or 'main')==setting]))
        for s in ('base','shock')} for m in methods} for setting in settings}
    profiles=[]
    for identity in sorted({t['input_id'] for t in tasks}):
        data=read(Path(inputs[identity]['path']))
        for trace,event in enumerate(data['events']):
            profiles.append(dict(input_id=identity,type=event['type'],unchanged=data['base'][trace][:200]==data['shock'][trace][:200],
                intervals=[dict(**part,base_total=sum(data['base'][trace][part['start']:part['end']]),
                    shock_total=sum(data['shock'][trace][part['start']:part['end']]),
                    actual_absolute_change=sum(abs(a-b) for a,b in zip(data['base'][trace][part['start']:part['end']],data['shock'][trace][part['start']:part['end']]))) for part in event['intervals']]))
    summary=dict(phase=phase,episodes=len(episodes),node_periods=len(episodes)*600,method_costs=means,comparisons=comparisons,
        actual_profiles=profiles,all_episode_results=episodes,all_cases_retained=True,
        no_training=True,primary_metric='200-period three-node mean I+B cost',
        limitations='Five frozen model seeds; report/notification/global state and candidate-search compute disclosed. D constant rule family differs from dynamic LLM rules. No standalone semantic or equal-compute causal claim.')
    write(OUTPUT/f'{phase}_summary.json',summary)
    # Include failed and successful attempts, not only final labels.
    phase_calls_root=OUTPUT/'phase_resources'/phase
    resources=summarize_resources(OUTPUT/'runs')
    write(OUTPUT/'cumulative_resources.json',resources)
    lines=[f'# 投稿必做实验：{phase}\n',f'完成{len(episodes)}回合、{len(episodes)*600}节点期。所有种子和配对保留。\n',
        '| 设置 | 方法 | 正常成本 | 冲击成本 |','|---|---|---:|---:|']
    for setting,row in means.items():
        for m,cost in row.items():lines.append(f"|{setting}|{m}|{cost['base']:.6f}|{cost['shock']:.6f}|")
    for right,c in comparisons.items():
        b=c['bootstrap'];lines.append(f"\n完整策略减{right}：均值{b['mean']:.6f}，{100*b['coverage']:.2f}%区间[{b['low']:.6f},{b['high']:.6f}]；改善{c['better']}，退化{c['worse']}。")
    lines.append('\n敏感性只作配对描述；开发与确认不混用。格式失败、回退、开销及全部不利案例保留。确定性搜索使用相同可见信息但额外候选构建算力，不能称等计算或单独语义证明。')
    (ROOT/f'docs/2026-10-09-required-{phase}-results.md').write_text('\n'.join(lines),encoding='utf-8')
    return summary
