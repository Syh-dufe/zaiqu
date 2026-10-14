"""Independent metrics from all saved point predictions, no inference."""
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/timesfm_forecast_pilot/development_v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
cases=read(OUT/'cases.json');predictions=read(OUT/'predictions.json')
assert len(cases)==len(predictions)==48
case_map={c['id']:c for c in cases};rows=[];metrics=[]
for prediction in predictions:
    case=case_map[prediction['case_id']];actual=case['future_label']
    for method,values in prediction['methods'].items():
        assert len(values)==20 and all(math.isfinite(v) and 0<=v<=20 for v in values)
        errors=[a-b for a,b in zip(values,actual)]
        block_errors=[]
        for start in range(-case['report_age'],20,3):
            if start<0 or start+3>20:continue
            block_errors.append(sum(errors[start:start+3])/3)
        actual_trend=sum(actual[-5:])/5-sum(actual[:5])/5
        predicted_trend=sum(values[-5:])/5-sum(values[:5])/5
        metrics.append(dict(case_id=case['id'],type=case['type'],method=method,mae=sum(abs(e) for e in errors)/20,rmse=math.sqrt(sum(e*e for e in errors)/20),bias=sum(errors)/20,block_mae=sum(abs(e) for e in block_errors)/len(block_errors),trend_error=abs(predicted_trend-actual_trend)))
        rows.extend(dict(case_id=case['id'],type=case['type'],method=method,offset=i,actual=actual[i],prediction=values[i]) for i in range(20))
groups=defaultdict(list)
for metric in metrics:
    groups['all',metric['method']].append(metric);groups[metric['type'],metric['method']].append(metric)
summary={}
for (kind,method),es in groups.items():
    summary.setdefault(kind,{})[method]={k:sum(e[k] for e in es)/len(es) for k in ('mae','rmse','bias','block_mae','trend_error')}
    summary[kind][method]['cases']=len(es)
gate=summary['all']['timesfm']['mae']<min(summary['all']['merton']['mae'],summary['all']['trend']['mae']) and all(summary[t]['timesfm']['mae']<=min(summary[t]['merton']['mae'],summary[t]['trend']['mae']) for t in summary if t!='all')
with (OUT/'period_predictions.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(OUT/'metrics.json').write_text(json.dumps(dict(summary=summary,gate_passed=gate,per_case=metrics),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(summary=summary,gate_passed=gate),ensure_ascii=False,indent=2))
