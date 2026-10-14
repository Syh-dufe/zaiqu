"""Recalculate all pilot errors from raw per-period CSV."""
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/timesfm_forecast_pilot/development_v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        while b:=f.read(8*1024*1024):h.update(b)
    return h.hexdigest()
cases=read(OUT/'cases.json');case_map={c['id']:c for c in cases}
raw=read(OUT/'predictions.json');metrics=read(OUT/'metrics.json')
rows=list(csv.DictReader((OUT/'period_predictions.csv').open(encoding='utf-8')))
assert len(rows)==3840
groups=defaultdict(list)
for r in rows:groups[r['case_id'],r['method']].append(r)
assert len(groups)==192
for metric in metrics['per_case']:
    rr=sorted(groups[metric['case_id'],metric['method']],key=lambda r:int(r['offset']))
    assert [int(r['offset']) for r in rr]==list(range(20))
    actual=[float(r['actual']) for r in rr];pred=[float(r['prediction']) for r in rr]
    assert actual==case_map[metric['case_id']]['future_label']
    error=[a-b for a,b in zip(pred,actual)]
    expected=dict(mae=sum(abs(x) for x in error)/20,rmse=math.sqrt(sum(x*x for x in error)/20),bias=sum(error)/20)
    assert all(abs(metric[k]-v)<1e-9 for k,v in expected.items())
prepared=read(OUT/'prepared.json')
for path,h in prepared['inputs_sha256'].items():
    data=read(path)
    for case in cases:
        if f"batch{case['batch']:02d}" not in path:continue
        end=case['decision_period']-1
        expected=[sum(data['shock'][case['trace']][i:i+3])/3 for i in range(0,end-end%3,3)]
        assert expected==case['block_history']
        assert case['report_age']==end%3
for p,h in read(OUT/'freeze.json')['sha256'].items():assert digest(p)==h,'Frozen file changed'
summary=metrics['summary'];gate=metrics['gate_passed'];runtime=read(OUT/'run_finished.json')
lines=['# TimesFM 2.5需求预测小规模开发试用','', '## 范围','', '2批已暴露开发输入×4冲击类型×6固定时点，共48窗口、8条路径。仅决策前已送达3期报告块均值输入；未送达片段不输入，真实未来仅作为评分标签。无DeepSeek调用、无训练、无库存闭环运行。窗口重叠，不把48当独立需求样本。','', '官方TimesFM2.5-200m checkpoint，revision1d952420fba87f3c6dee4f240de0f1a0fbc790e3，软件timesfm2.0.2，CPU两线程，冻结权重。它是后续2.5版本，不称ICML2024原checkpoint。官方代码与权重Apache2.0，来源：https://github.com/google-research/timesfm。','', '## 总体点预测结果','', '|方法|逐期MAE|平均窗口RMSE|偏差|完整未来报告块MAE|趋势误差|','|---|---:|---:|---:|---:|---:|']
for method in ('merton','naive','trend','timesfm'):
    a=summary['all'][method];lines.append(f"|{method}|{a['mae']:.6f}|{a['rmse']:.6f}|{a['bias']:+.6f}|{a['block_mae']:.6f}|{a['trend_error']:.6f}|")
lines+=['','## 各类型逐期MAE','', '|类型|Merton|最新值延续|趋势|TimesFM|','|---|---:|---:|---:|---:|']
for kind in ('single_surge','double_surge','sustained_surge','surge_then_drop'):
    a=summary[kind];lines.append(f"|{kind}|{a['merton']['mae']:.6f}|{a['naive']['mae']:.6f}|{a['trend']['mae']:.6f}|{a['timesfm']['mae']:.6f}|")
lines+=['','## 成对窗口结果','']
for ref in ('merton','naive','trend'):
    by_case={e['case_id']:e['mae'] for e in metrics['per_case'] if e['method']==ref}
    diffs=[e['mae']-by_case[e['case_id']] for e in metrics['per_case'] if e['method']=='timesfm']
    lines.append(f"- TimesFM vs {ref}: 改善{sum(x<-1e-9 for x in diffs)}，退化{sum(x>1e-9 for x in diffs)}，相同{sum(abs(x)<=1e-9 for x in diffs)}；平均MAE差{sum(diffs)/len(diffs):+.6f}。")
lines+=['', '## 开销与独立核验','',f"模型加载及试用墙钟{runtime['elapsed_seconds']:.3f}秒，12批推理累计{runtime['inference_seconds']:.3f}秒；不含下载、依赖安装和输入注册。权重925181104字节，独立缓存未修改原训练venv。全部3840预测行重算MAE/RMSE/偏差一致，输入仅已送达报告检查通过，冻结文件SHA一致。",'', '## 预登记门槛与解释','',f"进入另行登记路径构造/闭环开发门槛通过：{gate}。要求TimesFM总体MAE严格低于Merton和趋势，四类型均不高于这两参照。门槛未通过不得直接接入正式决策实验，不针对这48窗口调版本或窗口到胜出。",'', '三期报告均值预测重复至逐期，仅表达块平均，无法恢复块内真实次序。点预测或逐点分位不是联合未来路径；本次不把它们独立随机抽样用于库存仿真。预测合格也不证明成本改善，未见泛化、语义价值或完整机制贡献。原始预测、分位输出、每案例指标与全部不利结果保留。']
(OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
files=['cases.json','prepared.json','freeze.json','model_loaded.json','predictions.json','metrics.json','period_predictions.csv','run_finished.json','report.md']
(OUT/'completed.json').write_text(json.dumps(dict(status='complete',cases=48,rows=3840,api=0,training=0,gate_passed=gate,independent_metrics_check=True,input_causality_check=True,source_unchanged=True,sha256={f:digest(OUT/f) for f in files}),ensure_ascii=False,indent=2),encoding='utf-8')
print('\n'.join(lines))
