"""All five models, two exposed paths; never treat models as new demand paths."""
def summarize(runner,out,finished,common):
 core=runner.core;old=runner.ROOT/'results/sundial_closed_loop_development/development_v2/runs';episodes=[]
 for seed in range(11,16):
  directory=old/f'batch01_seed{seed}' if seed<13 else out/'runs'/next(t['label'] for t in finished if t['seed']==seed)
  data=core.read(directory/'demands.json')
  for e in core.read(directory/'episodes.json'):
   if e['group'] in runner.METHODS and e['trace'] in runner.SELECTED:episodes.append(dict(**e,seed=seed,type=data['events'][e['trace']]['type'],reused=seed<13))
 assert len(episodes)==40 and len({(e['seed'],e['group'],e['trace'],e['scenario']) for e in episodes})==40
 pairs=[];lookup={(e['seed'],e['group'],e['trace'],e['scenario']):e for e in episodes}
 for seed in range(11,16):
  for trace in runner.SELECTED:
   a=lookup[seed,'adapted_sundial',trace,'shock'];o=lookup[seed,'original_merton',trace,'shock'];delta=a['cost']-o['cost']
   pairs.append(dict(seed=seed,trace=trace,type=a['type'],old_cost=o['cost'],new_cost=a['cost'],difference=delta,reduction_percent=-100*delta/o['cost'],
    did=delta-(lookup[seed,'adapted_sundial',trace,'base']['cost']-lookup[seed,'original_merton',trace,'base']['cost'])))
 types={}
 for kind in sorted({p['type'] for p in pairs}):
  local=[p for p in pairs if p['type']==kind];o=sum(p['old_cost'] for p in local)/5;a=sum(p['new_cost'] for p in local)/5
  types[kind]=dict(old_cost=o,new_cost=a,difference=a-o,reduction_percent=100*(o-a)/o,improved=sum(p['difference']<0 for p in local),tied=sum(p['difference']==0 for p in local),worse=sum(p['difference']>0 for p in local))
 calls=common.calls_under(out/'runs');summary=dict(episodes=40,node_periods=24000,new_episodes=24,reused_episodes=16,independent_demand_paths=2,all_episodes=episodes,pairs=pairs,type_means=types,
 new_http=len(calls),new_semantic=sum(c.get('attempt')==1 for c in calls),usage=common.usage(calls),post_selected_development=True,no_training=True,not_independent_confirmation=True)
 core.write(out/'summary.json',summary)
 lines=['# 双峰与突增后回落五模型补齐结果','','seed11/12复用审核数据，仅seed13..15新增。两个已暴露Poisson需求路径，类型是在看过初步结果后选出；仅检验跨五模型表现，不能作为一般性独立确认。','','|场景|seed|旧Merton成本|修正Sundial成本|成本降低%|','|---|---:|---:|---:|---:|']
 for p in pairs:lines.append(f"|{p['type']}|{p['seed']}|{p['old_cost']:.6f}|{p['new_cost']:.6f}|{p['reduction_percent']:.3f}| ")
 lines+=['','|场景|旧均值|新均值|降低%|改善/持平/退化|','|---|---:|---:|---:|---|']
 for kind,v in types.items():lines.append(f"|{kind}|{v['old_cost']:.6f}|{v['new_cost']:.6f}|{v['reduction_percent']:.3f}|{v['improved']}/{v['tied']}/{v['worse']}|")
 lines+=['',f"新增HTTP{summary['new_http']}、语义{summary['new_semantic']}，所有部分/恢复费用计入；旧原批273HTTP另列，复用没有新调用。",'原Sundial和失败误差校准不作为本次新模型，沿用已冻结24参数适配器。','原提示历史Merton描述保留，实际预测及分配有完整审计；LLM回复不同导致候选不同，系统成本改善不能单独归因预测器。','全部五seed与不利结果、normal/DID保留。原480回合批保持用户停止，不扩展其它背景/类型。']
 (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');return summary
