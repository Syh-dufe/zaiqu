"""Full cost contrasts; sparse development paths are not confirmation evidence."""
def summarize(runner,out,finished,common):
 core=runner.core;episodes=[]
 for task in finished:
  for e in core.read(out/'runs'/task['label']/'episodes.json'):
   data=core.read(out/'runs'/task['label']/'demands.json')
   episodes.append(dict(**e,batch=task['batch'],seed=task['seed'],background=task['background'],type=data['events'][e['trace']]['type']))
 assert len(episodes)==480 and len({(e['group'],e['scenario'],e['seed'],e['batch'],e['trace']) for e in episodes})==480
 def means(selected):return {m:{k:sum(e[k] for e in selected if e['group']==m)/sum(e['group']==m for e in selected) for k in ('cost','downstream_backlog')} for m in runner.METHODS}
 shock=[e for e in episodes if e['scenario']=='shock'];overall=means(shock)
 backgrounds={b:means([e for e in shock if e['background']==b]) for b in ('stationary','trend','periodic')}
 cells={b+'_'+t:means([e for e in shock if e['background']==b and e['type']==t]) for b in backgrounds for t in sorted({e['type'] for e in shock})}
 seeds={str(s):means([e for e in shock if e['seed']==s]) for s in range(11,16)}
 a=overall['adapted_sundial'];o=overall['original_merton']
 gate=all(a['cost']<overall[m]['cost'] for m in runner.METHODS if m!='adapted_sundial') and a['downstream_backlog']<=o['downstream_backlog'] and not any(v['adapted_sundial']['cost']>v['original_merton']['cost'] and v['adapted_sundial']['downstream_backlog']>v['original_merton']['downstream_backlog'] for v in cells.values())
 lookup={(e['group'],e['scenario'],e['seed'],e['batch'],e['trace']):e for e in episodes};pairs=[]
 for e in shock:
  if e['group']!='adapted_sundial':continue
  pairs.append(dict(seed=e['seed'],batch=e['batch'],trace=e['trace'],background=e['background'],type=e['type'],cost=e['cost'],
    cost_differences={m:e['cost']-lookup[m,'shock',e['seed'],e['batch'],e['trace']]['cost'] for m in runner.METHODS if m!='adapted_sundial'},
    did={m:(e['cost']-lookup['adapted_sundial','base',e['seed'],e['batch'],e['trace']]['cost'])-(lookup[m,'shock',e['seed'],e['batch'],e['trace']]['cost']-lookup[m,'base',e['seed'],e['batch'],e['trace']]['cost']) for m in runner.METHODS if m!='adapted_sundial'}))
 calls=common.calls_under(out/'runs');summary=dict(episodes=480,node_periods=288000,shock_means=overall,background_means=backgrounds,cell_means=cells,seed_means=seeds,
   pairs=pairs,all_episodes=episodes,fixed_gate_passed=bool(gate),http=len(calls),semantic=sum(c.get('attempt')==1 for c in calls),usage=common.usage(calls),development_only=True,independent_paths=12,no_training=True,not_significance_or_generalization=True)
 core.write(out/'summary.json',summary)
 lines=['# Sundial闭环成本开发结果','','12条已暴露需求路径、五模型、四方法normal/shock，共480回合。API现场回复差异及预测计算差异披露；不作独立确认或语义贡献宣称。','','|范围|系统|冲击平均成本|','|---|---|---:|']
 for scope,values in [('总体',overall)]+list(backgrounds.items()):
  for m in runner.METHODS:lines.append(f"|{scope}|{m}|{values[m]['cost']:.6f}|")
 lines+=['',f'固定开发门槛：{bool(gate)}。','原Sundial与修正版共享原始采样和三期总量约束分配；Merton和最新值保留原逐期路径机制，路径分布/计算量不同。','原提示中的Merton历史描述未修改，实际预测来源记录于forecast_audit。','全部60配对、12背景/类型格、五seed、normal/DID与不利结果保留在summary.json。未进行大批独立确认。']
 (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');return summary
