"""Independent distribution metrics from saved Stage-A paths."""
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/timesfm_path_development/development_v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

records=read(OUT/'paths.json');assert len(records)==48 and len({r['case_id'] for r in records})==48
per_case=[]
for r in records:
    assert set(r['methods'])=={'original_merton','merton','naive','timesfm'}
    y=np.asarray(r['actual']);assert y.shape==(20,)
    for method,data in r['methods'].items():
        x=np.asarray(data['paths']);raw=np.asarray(data['raw']);a=np.asarray(data['center'])
        assert x.shape==raw.shape==(32,20) and ((x>=0)&(x<=20)).all()
        assert len(set(data['stream_seeds']))==2
        assert data['deployment']==np.concatenate([x[:3],x[16:19]]).tolist()
        mae=float(np.abs(x.mean(axis=0)-y).mean())
        # Empirical CRPS including all ordered path pairs, with replacement.
        crps=float((np.abs(x-y).mean(axis=0)-.5*np.abs(x[:,None,:]-x[None,:,:]).mean(axis=(0,1))).mean())
        total_error=float(abs(x.sum(axis=1).mean()-y.sum()))
        corr=[float(np.corrcoef(row[:-1],row[1:])[0,1]) for row in x if row[:-1].std()>0 and row[1:].std()>0]
        per_case.append(dict(case_id=r['case_id'],type=r['type'],method=method,crps=crps,mae=mae,total_demand_absolute_error=total_error,boundary_share=float(((x==0)|(x==20)).mean()),raw_clipped_share=float(((raw<0)|(raw>20)).mean()),center_bias=float((x.mean(axis=0)-a).mean()),lag1_correlation=float(np.mean(corr)) if corr else None))
summary={}
for kind in ['all']+sorted({r['type'] for r in records}):
    summary[kind]={}
    for method in ('original_merton','merton','naive','timesfm'):
        rows=[r for r in per_case if r['method']==method and (kind=='all' or r['type']==kind)]
        summary[kind][method]={k:float(np.mean([r[k] for r in rows if r[k] is not None])) if any(r[k] is not None for r in rows) else None for k in ('crps','mae','total_demand_absolute_error','boundary_share','raw_clipped_share','center_bias','lag1_correlation')}
        summary[kind][method]['windows']=len(rows)
t=summary['all']['timesfm'];m=summary['all']['merton'];n=summary['all']['naive']
gate=t['crps']<m['crps'] and t['mae']<m['mae'] and not any(summary[k]['timesfm']['crps']>summary[k]['merton']['crps'] and summary[k]['timesfm']['mae']>summary[k]['merton']['mae'] for k in summary if k!='all') and not (t['crps']>=n['crps'] and t['mae']>=n['mae'])
for name,expected in read(OUT/'freeze.json')['sha256'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected,name
write(OUT/'metrics.json',dict(summary=summary,per_case=per_case,gate_passed=bool(gate)))
lines=['# TimesFM路径构造：阶段A无API开发诊断','','48重叠窗口、8已暴露需求路径；每方法32模拟路径不增加真实样本数。原Merton参照是原公开转移分布32路径，不是原6路径逐值重现。','','|方法|CRPS|路径均值MAE|20期总需求绝对误差|边界占比|','|---|---:|---:|---:|---:|']
for method,row in summary['all'].items():lines.append(f"|{method}|{row['crps']:.6f}|{row['mae']:.6f}|{row['total_demand_absolute_error']:.6f}|{row['boundary_share']:.2%}|")
lines+=['',f'固定阶段A门槛通过：{bool(gate)}。','仅预测分布开发证据；无API、无训练、无库存闭环，不能称成本改善或未见泛化。','各类型、每窗口和不利结果全部保存在metrics.json。冻结文件哈希一致。']
(OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
write(OUT/'completed.json',dict(cases=48,method_windows=192,generated_values=122880,gate_passed=bool(gate),freeze_verified=True,api=0,training=0))
print(json.dumps(dict(summary=summary,gate_passed=bool(gate)),ensure_ascii=False,indent=2))
