"""Same complete-report-block comparisons, no model inference or API."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_forecast_pilot/development_v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def crps(x,y):return float((np.abs(x-y).mean(axis=0)-.5*np.abs(x[:,None,:]-x[None,:,:]).mean(axis=(0,1))).mean())
cases=read(ROOT/'results/timesfm_forecast_pilot/development_v1/cases.json')
prior={r['case_id']:r for r in read(ROOT/'results/timesfm_path_development/development_v1/paths.json')}
pred={r['case_id']:r for r in read(OUT/'predictions.json')};assert len(pred)==48
rows=[];scoring=[]
for c in cases:
 y=np.asarray(c['future_label']);starts=[s for s in range(-c['report_age'],20,3) if s>=0 and s+3<=20]
 labels=np.asarray([y[s:s+3].mean() for s in starts])
 methods={name:np.asarray(prior[c['id']]['methods'][old]['paths'],dtype=float) for name,old in [('merton','original_merton'),('naive','naive'),('timesfm','timesfm')]}
 methods['sundial']=np.asarray(pred[c['id']]['period_paths'])
 for method,values in methods.items():
  blocks=np.stack([values[:,s:s+3].mean(axis=1) for s in starts],axis=1)
  assert blocks.shape==(32,len(starts))
  metric=dict(case_id=c['id'],type=c['type'],method=method,block_crps=crps(blocks,labels),block_mae=float(np.abs(blocks.mean(axis=0)-labels).mean()),period_mae=float(np.abs(values.mean(axis=0)-y).mean()),total_crps=crps(values.sum(axis=1)[:,None],np.asarray([y.sum()])),boundary_share=float(((values<=0)|(values>=20)).mean()))
  rows.append(metric);scoring.append(dict(case_id=c['id'],method=method,block_samples=blocks.tolist(),block_labels=labels.tolist(),period_samples=values.tolist(),period_labels=y.tolist()))
summary={}
for kind in ['all']+sorted({c['type'] for c in cases}):
 summary[kind]={}
 for method in ('merton','naive','timesfm','sundial'):
  local=[r for r in rows if r['method']==method and (kind=='all' or r['type']==kind)]
  summary[kind][method]={k:float(np.mean([r[k] for r in local])) for k in ('block_crps','block_mae','period_mae','total_crps','boundary_share')}
s=summary['all']['sundial']
gate=all(s['block_crps']<summary['all'][m]['block_crps'] and s['block_mae']<summary['all'][m]['block_mae'] for m in ('merton','naive','timesfm')) and not any(summary[k]['sundial']['block_crps']>summary[k]['merton']['block_crps'] and summary[k]['sundial']['block_mae']>summary[k]['merton']['block_mae'] for k in summary if k!='all')
write(OUT/'metrics.json',dict(summary=summary,per_case=rows,gate_passed=bool(gate)))
write(OUT/'scoring_values.json',scoring)
print(json.dumps(dict(summary=summary,gate_passed=bool(gate)),ensure_ascii=False,indent=2))
