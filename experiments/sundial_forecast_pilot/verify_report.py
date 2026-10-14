"""Independent scalar sorted-CRPS audit and freeze check; no inference."""
import hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_forecast_pilot/development_v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
metrics=read(OUT/'metrics.json');values=read(OUT/'scoring_values.json');assert len(values)==192
lookup={(r['case_id'],r['method']):r for r in metrics['per_case']}
for r in values:
 x=r['block_samples'];y=r['block_labels'];n=len(x);score=error=0
 for j,actual in enumerate(y):
  ordered=sorted(p[j] for p in x)
  score+=sum(abs(v-actual) for v in ordered)/n-sum((2*i-n+1)*v for i,v in enumerate(ordered))/(n*n)
  error+=abs(sum(ordered)/n-actual)
 saved=lookup[r['case_id'],r['method']]
 assert math.isclose(score/len(y),saved['block_crps'],abs_tol=1e-9)
 assert math.isclose(error/len(y),saved['block_mae'],abs_tol=1e-9)
for name,sha in read(OUT/'freeze.json')['sha256'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==sha,name
result=dict(cases=48,case_methods=192,scalar_block_crps_mae_recomputed=True,source_model_dependencies_unchanged=True,api=0,training=0,gate_passed=metrics['gate_passed'])
(OUT/'completed.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
lines=['# Sundial零样本轨迹预测开发结果','','48重叠窗口，8条已暴露路径；每窗口32生成样本。无API、无训练、无库存闭环。','','|方法|完整报告块CRPS↓|报告块均值MAE↓|辅助逐期均值MAE↓|','|---|---:|---:|---:|']
for m,v in metrics['summary']['all'].items():lines.append(f"|{m}|{v['block_crps']:.6f}|{v['block_mae']:.6f}|{v['period_mae']:.6f}|")
lines+=['',f"固定开发门槛通过：{metrics['gate_passed']}。",'Sundial输入和输出单位为三期需求均值；重复至逐期仅用于辅助评分，不能恢复块内真实顺序，不能直接当整数需求闭环执行。','全部类型和不利窗口保留；预测样本不增加独立真实需求数。CPU开销见run_finished.json；官方默认50采样步，冻结128M模型，无微调。','全部192方法窗口的报告块CRPS/MAE独立复算一致，模型源码依赖与输入SHA一致；仅预测开发证据，不证明成本改善。']
(OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(result))
