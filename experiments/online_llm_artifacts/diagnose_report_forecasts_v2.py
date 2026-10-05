"""Post-hoc forecast diagnostics only; never supplied to API and no policy changes."""
import csv,json,statistics,hashlib
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'results/online_llm_report_trigger/development_v2'
EXPORT=ROOT/'docs/artifacts/online_llm_report_trigger_development_v2'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))

def main():
    output=EXPORT/'forecast_diagnosis.json'
    assert not output.exists(),'Refuse overwrite'
    groups=defaultdict(list)
    for folder in (SOURCE/'runs').iterdir():
        if not folder.is_dir():continue
        data=read(folder/'demands.json')
        with (folder/'periods.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
        actual={(r['group'],int(r['trace']),int(r['period'])):float(r['demand']) for r in rows if r['scenario']=='shock' and r['node']=='0'}
        for s in read(folder/'scores.json'):
            if not s.get('generation_event'):continue
            paths=s['forecasts'][0]+s['forecasts'][1];horizon=len(paths[0]);period=s['decision_period']
            truth=[actual[s['group'],s['trace'],t] for t in range(period,period+horizon)]
            predicted=[statistics.mean(path[t] for path in paths) for t in range(horizon)]
            mean_error=statistics.mean(predicted)-statistics.mean(truth)
            mae=statistics.mean(abs(p-t) for p,t in zip(predicted,truth))
            event=data['events'][s['trace']];phase='first40' if period<event['start_index']+43 else 'later'
            groups[s['group'],event['type'],phase].append(dict(bias=mean_error,MAE=mae,selected_nonzero=s['chosen']!='zero'))
    result=dict(development_only=True,post_hoc=True,no_API_calls=True,actual_future_used_for_analysis_only=True,
        metric='20-period (or remaining shorter horizon) mean error across6 synthetic paths versus realized exogenous demand; no correction counterfactual claim',
        cells=[dict(method=k[0],type=k[1],phase=k[2],events=len(v),forecast_bias=statistics.mean(x['bias'] for x in v),
            forecast_MAE=statistics.mean(x['MAE'] for x in v),nonzero_selected=sum(x['selected_nonzero'] for x in v)) for k,v in sorted(groups.items())])
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    h=read(EXPORT/'export_hashes.json');h['archive_sha256'][output.name]=hashlib.sha256(output.read_bytes()).hexdigest()
    (EXPORT/'export_hashes.json').write_text(json.dumps(h,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
