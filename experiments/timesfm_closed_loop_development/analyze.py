"""Complete development contrasts, explicit fixed go/no-go criteria."""
def summarize(runner,out,finished,common):
    core=runner.core;episodes=[]
    for task in finished:
        directory=out/'runs'/task['label'];data=core.read(directory/'demands.json')
        for e in core.read(directory/'episodes.json'):
            episodes.append(dict(**e,batch=task['batch'],seed=task['seed'],type=data['events'][e['trace']]['type']))
    assert len(episodes)==320
    assert len({(e['group'],e['scenario'],e['seed'],e['batch'],e['trace']) for e in episodes})==320
    def means(kind=None,seed=None):
        selected=[e for e in episodes if e['scenario']=='shock' and (kind is None or e['type']==kind) and (seed is None or e['seed']==seed)]
        return {m:{k:sum(e[k] for e in selected if e['group']==m)/sum(e['group']==m for e in selected) for k in ('cost','downstream_backlog')} for m in runner.METHODS}
    overall=means();types={t:means(t) for t in sorted({e['type'] for e in episodes})};seeds={str(s):means(seed=s) for s in range(11,16)}
    t=overall['center_timesfm'];o=overall['original_merton']
    gate=all(t['cost']<overall[m]['cost'] for m in runner.METHODS if m!='center_timesfm') and t['downstream_backlog']<=o['downstream_backlog'] and not any(v['center_timesfm']['cost']>v['original_merton']['cost'] and v['center_timesfm']['downstream_backlog']>v['original_merton']['downstream_backlog'] for v in types.values())
    pairs=[]
    lookup={(e['group'],e['seed'],e['batch'],e['trace']):e for e in episodes if e['scenario']=='shock'}
    for e in episodes:
        if e['scenario']!='shock' or e['group']!='center_timesfm':continue
        pairs.append(dict(seed=e['seed'],batch=e['batch'],trace=e['trace'],type=e['type'],cost=e['cost'],cost_differences={m:e['cost']-lookup[m,e['seed'],e['batch'],e['trace']]['cost'] for m in runner.METHODS if m!='center_timesfm'}))
    calls=common.calls_under(out/'runs')
    summary=dict(episodes=320,node_periods=192000,shock_means=overall,type_means=types,seed_means=seeds,pairs=pairs,
        fixed_gate_passed=bool(gate),all_episodes=episodes,http=len(calls),semantic=sum(c.get('attempt')==1 for c in calls),usage=common.usage(calls),
        development_only=True,independent_paths=8,no_training=True,not_significance_or_generalization=True)
    core.write(out/'summary.json',summary)
    lines=['# TimesFM闭环开发结果','','五种子、两批已暴露需求、四类型、四组系统、normal/shock，共320回合。各组LLM重新现场调用，API回复差异无法完全归因预测器。','','|系统|冲击平均成本|','|---|---:|']
    for m in runner.METHODS:lines.append(f"|{m}|{overall[m]['cost']:.6f}|")
    lines+=['',f'预登记开发门槛通过：{bool(gate)}。','每类型、每种子和全部40冲击配对差异保留于summary.json。正常/通知前等冻结HAPPO，权重不更新。','原SYSTEM与提示原样保留，包括历史Merton预测描述；新组实际路径构造在审计中明确登记，此描述不作为新预测器技术说明。']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return summary
