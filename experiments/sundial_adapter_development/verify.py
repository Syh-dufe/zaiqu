import math
import numpy as np
from common import ROOT,OUT,read,write,digest,verify_freeze,trace_hash,module
from adapter import features,transform
def verify():
 metrics=read(OUT/'metrics.json');lookup={(r['case_id'],r['method']):r for r in metrics['per_case']};scoring=read(OUT/'scoring_values.json');assert len(scoring)==480
 for r in scoring:
  x=r['block_samples'];y=r['labels'];n=32;value=err=0
  for j,a in enumerate(y):
   v=sorted(row[j] for row in x);value+=sum(abs(z-a) for z in v)/n-sum((2*i-n+1)*z for i,z in enumerate(v))/n**2;err+=abs(sum(v)/n-a)
  s=lookup[r['case_id'],r['method']];assert math.isclose(value/len(y),s['crps'],abs_tol=1e-9) and math.isclose(err/len(y),s['mae'],abs_tol=1e-9)
 used=set(read(OUT/'historical.json')['consumed_hashes'])
 for phase in ('development','test'):
  prepared=read(OUT/('prepared.json' if phase=='development' else 'test_prepared.json'))
  assert digest(OUT/f'{phase}_cases.json')==prepared['cases_sha256'] and digest(OUT/f'{phase}_inputs.json')==prepared['input_sha256']
  for data in read(OUT/f'{phase}_inputs.json'):
   for trace in range(4):
    pair={trace_hash(data[s][trace]) for s in ('base','shock')};assert not pair&used;used.update(pair)
 reports=module('adapter_independent_reports',ROOT/'experiments/deepseek_refinement/reports.py')
 for phase in ('development','test'):
  inputs=read(OUT/f'{phase}_inputs.json')
  for c in read(OUT/f'{phase}_cases.json'):
   data=inputs[c['batch']-1]['shock'][c['trace']];r=reports.DemandReports(3)
   for index,d in enumerate(data[:c['decision_period']-1],1):r.observe(d,index)
   assert c['block_history']==[d['demand_mean'] for d in r.deliveries] and c['report_age']==r.age
 fit=read(OUT/'fit_completed.json');best=read(OUT/'best_adapter.json');curve=read(OUT/'fit_curve.json');assert best['selected_epoch']==min(curve,key=lambda r:r['dev_crps'])['epoch']
 assert digest(OUT/'best_adapter.json')==fit['best_sha256']==read(OUT/'test_registration.json')['adapter_sha256']
 types=sorted({p['type'] for p in metrics['paths']});diff=[np.asarray([[p['means']['adapted']['crps']-p['means'][m]['crps'] for m in ('sundial','merton')] for p in metrics['paths'] if p['type']==t]) for t in types]
 rng=np.random.default_rng(20271951);samples=[]
 for _ in range(20000):
  ids=rng.integers(0,5,size=(4,5));samples.append(sum(diff[t][ids[t]].mean(axis=0) for t in range(4))/4)
 for i,m in enumerate(('sundial','merton')):assert np.allclose(np.quantile(np.asarray(samples)[:,i],[.0125,.9875]),metrics['contrasts'][m]['ci_97_5'],atol=1e-12,rtol=0)
 verify_freeze();write(OUT/'completed.json',dict(train_paths=24,dev_paths=8,test_paths=20,test_windows=120,case_methods=480,raw_metrics_verified=True,bootstrap_verified=True,models_frozen=True,adapter_parameters=24,gate_passed=metrics['gate_passed'],api=0))
 lines=['# Sundial场景输出适配试用','','24新训练路径、8新开发路径；开发CRPS选24参数适配器后冻结，再生成20新验证路径/120窗口。Sundial128M与HAPPO冻结，无API，无订货闭环。','','|方法|报告块CRPS↓|报告块均值MAE↓|','|---|---:|---:|']
 for m,v in metrics['overall'].items():lines.append(f"|{m}|{v['crps']:.6f}|{v['mae']:.6f}|")
 lines+=['',f"最佳开发epoch={fit['selected_epoch']}，停止原因={fit['stop_reason']}；推进门槛通过={metrics['gate_passed']}。",'','|适配Sundial减参照CRPS|平均差|两侧97.5%区间|','|---|---:|---|']
 for m,v in metrics['contrasts'].items():lines.append(f"|{m}|{v['mean']:.6f}|[{v['ci_97_5'][0]:.6f},{v['ci_97_5'][1]:.6f}]|")
 lines+=['','借鉴COSA输出门控残差思路并自行扩展尺度校正，不是官方COSA/Sundial实现。只做离线适配器训练，无测试时参数更新，无跨测试回合学习；报告块轨迹不恢复块内逐期顺序。','以需求路径分层重采样20000次，两主比较Bonferroni，保留全部类型/路径/退化。基础需求由Merton生成，结论限本设定，不证明订货成本改善。']
 (OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print('ADAPTER_INDEPENDENT_VERIFICATION_PASSED',flush=True)
if __name__=='__main__':verify()
