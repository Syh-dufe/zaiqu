"""Scalar metrics, independent bootstrap iteration and causal reconstruction."""
import math
import numpy as np
from common import ROOT,OUT,read,write,module,verify_freeze
def run():
 metrics=read(OUT/'metrics.json');lookup={(r['case_id'],r['method']):r for r in metrics['per_case']}
 values=read(OUT/'scoring_values.json');assert len(values)==240
 for r in values:
  x=r['block_samples'];y=r['block_labels'];n=len(x);score=mae=0
  for j,a in enumerate(y):
   v=sorted(row[j] for row in x);score+=sum(abs(z-a) for z in v)/n-sum((2*i-n+1)*z for i,z in enumerate(v))/(n*n);mae+=abs(sum(v)/n-a)
  expected=lookup[r['case_id'],r['method']]
  assert math.isclose(score/len(y),expected['block_crps'],abs_tol=1e-9) and math.isclose(mae/len(y),expected['block_mae'],abs_tol=1e-9)
 inputs=read(OUT/'inputs.json');cases=read(OUT/'cases.json');reports=module('sundial_verify_causal_reports',ROOT/'experiments/deepseek_refinement/reports.py')
 for c in cases:
  r=reports.DemandReports(3);demands=inputs[c['batch']-1]['shock'][c['trace']]
  for index,value in enumerate(demands[:c['decision_period']-1],1):r.observe(value,index)
  assert c['block_history']==[d['demand_mean'] for d in r.deliveries] and c['report_age']==r.age
  assert c['future_label']==demands[c['decision_period']-1:c['decision_period']+19]
 types=sorted(metrics['by_type']);arrays=[np.asarray([[p['difference'][k] for k in ('block_crps','block_mae')] for p in metrics['paths'] if p['type']==t]) for t in types]
 rng=np.random.default_rng(20271751);samples=[]
 for _ in range(20000):
  idx=rng.integers(0,5,size=(4,5));samples.append(sum((arrays[t][idx[t]].mean(axis=0) for t in range(4)))/4)
 for i,k in enumerate(('block_crps','block_mae')):assert np.allclose(np.quantile(np.asarray(samples)[:,i],[.0125,.9875]),metrics['contrasts'][k]['ci_97_5'],atol=1e-12,rtol=0)
 verify_freeze();write(OUT/'completed.json',dict(paths=20,cases=120,method_windows=240,api=0,training=0,causal_reports_verified=True,raw_metrics_recomputed=True,bootstrap_independently_recomputed=True,strong_prediction_support=metrics['strong_prediction_support']))
 lines=['# Sundial对Merton扩大预测验证','','20条查重新需求路径，四类型各5；每路径6重叠窗口，共120窗口。模型冻结，无API与训练。','','|方法|完整报告块CRPS↓|报告块均值MAE↓|','|---|---:|---:|']
 for m,v in metrics['overall'].items():lines.append(f"|{m}|{v['block_crps']:.6f}|{v['block_mae']:.6f}|")
 lines+=['','## 两项主比较：Sundial减Merton','','|指标|平均差|两侧97.5%区间|','|---|---:|---|']
 for k,v in metrics['contrasts'].items():lines.append(f"|{k}|{v['mean']:.6f}|[{v['ci_97_5'][0]:.6f}, {v['ci_97_5'][1]:.6f}]|")
 lines+=['',f"预登记较强总体预测支持条件：{metrics['strong_prediction_support']}。",'两项主比较采用Bonferroni控制，20000分层配对bootstrap，重采样单位是每类型五需求路径，不是120窗口或模型生成样本。','看过旧开发结果后登记的新扩大验证，旧未通过门槛结果保留；本轮不改变旧结论。只涉及预测，无实际订货成本结果，不自动启动付费闭环。','全部20路径、四类型与240方法窗口指标、原预测样本、碰撞清单、模型及源hash保留。']
 (OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print('EXPANDED_INDEPENDENT_VERIFICATION_PASSED',flush=True)
if __name__=='__main__':run()
