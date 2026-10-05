"""Same-event prediction diagnostics; no API, policy evaluation or training."""
import argparse
import ast
import hashlib
import json
import csv
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'results/online_llm_report_trigger/development_v2'
OUT=ROOT/'results/forecast_diagnosis/paired_v1'
PLAN=ROOT/'docs/superpowers/plans/2026-10-05-paired-forecast-diagnosis.md'
SHADOW=ROOT/'experiments/deepseek_refinement/shadow.py'

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2),encoding='utf-8')

def register():
    assert not OUT.exists(),'Refuse registration overwrite'
    done=read(SOURCE/'completed.json');assert done['episodes']==240 and done['node_periods']==144000
    assert sha(SOURCE/'summary.json')==done['summary_sha256']
    progress=read(SOURCE/'progress.json');assert len(progress['completed_runs'])==10
    files=[Path(__file__),PLAN,SHADOW,SOURCE/'completed.json',SOURCE/'summary.json',SOURCE/'freeze.json']
    paths=[]
    for item in progress['completed_runs']:
        folder=SOURCE/'runs'/item['run_label'];paths.append(str(folder.relative_to(ROOT)))
        files.extend(folder/name for name in ('scores.json','delivered_reports.json','periods.csv','demands.json','completed.json'))
    OUT.mkdir(parents=True)
    write(OUT/'freeze.json',dict(source_sha256={str(p.relative_to(ROOT)):sha(p) for p in files},
        parent_phase='exposed_development',API_calls=0,training_updates=0,expected_events=320,
        primary='same-event MAE of six-path mean; no significance or closed-loop claim'))
    write(OUT/'manifest.json',dict(runs=paths,freeze_sha256=sha(OUT/'freeze.json'),expected_events=320))
    print('REGISTERED_NO_API events=320')

def metrics(paths,truth):
    x=np.array(paths,dtype=float);y=np.array(truth,dtype=float)
    assert x.shape==(6,len(y))
    return dict(point_MAE=float(np.abs(x.mean(axis=0)-y).mean()),bias=float((x.mean(axis=0)-y).mean()),
        mean_path_MAE=float(np.abs(x-y).mean()),range_coverage=float(((y>=x.min(axis=0))&(y<=x.max(axis=0))).mean()))

def run():
    assert not any((OUT/name).exists() for name in ('events.json','completed.json','failed.json')),'Refuse repeat'
    manifest=read(OUT/'manifest.json');frozen=read(OUT/'freeze.json')
    assert sha(OUT/'freeze.json')==manifest['freeze_sha256']
    for rel,h in frozen['source_sha256'].items():assert sha(ROOT/rel)==h,rel
    text=SHADOW.read_text(encoding='utf-8');tree=ast.parse(text)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='forecasts')
    namespace={'np':np};exec(compile(ast.Module(body=[node],type_ignores=[]),str(SHADOW),'exec'),namespace)
    forecast=namespace['forecasts'];events=[]
    for raw in manifest['runs']:
        folder=ROOT/raw;reports=read(folder/'delivered_reports.json');data=read(folder/'demands.json')
        with (folder/'periods.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
        actual={(r['group'],int(r['trace']),int(r['period'])):int(r['demand']) for r in rows if r['scenario']=='shock' and r['node']=='0'}
        for s in read(folder/'scores.json'):
            if not s.get('generation_event'):continue
            period=s['decision_period']-1;group=s['group'];trace=s['trace']
            visible=[r for r in reports if r['group']==group and r['scenario']=='shock' and r['trace']==trace and r['end_period']<=period]
            assert [r['end_period'] for r in visible]==list(range(3,period+1,3))
            history=[r['demand_mean'] for r in visible for _ in range(3)]
            through=visible[-1]['end_period'] if visible else 0;age=period-through
            assert len(history)==through and 0<=age<=2
            public=s['context']['available_report'];assert public['observed_periods']==period and public['delivered_through_period']==through
            merton=forecast(history,trace,period,'merton',age)
            assert [merton[0],merton[1]]==s['forecasts'],'Original prediction reconstruction failed'
            residual=forecast(history,trace,period,'residual',age)
            horizon=min(20,200-period);truth=[actual[group,trace,t] for t in range(period+1,period+1+horizon)]
            event=dict(run=folder.name,source_method=group,trace=trace,decision_period=period+1,
                type=data['events'][trace]['type'],report_age=age,delivered_through=through,original_reproduced=True,
                merton_paths=merton,residual_paths=residual,actual_future_analysis_only=truth,
                merton=metrics(merton[0]+merton[1],truth),residual=metrics(residual[0]+residual[1],truth))
            event['point_MAE_delta']=event['residual']['point_MAE']-event['merton']['point_MAE'];events.append(event)
    assert len(events)==320 and len({(e['run'],e['source_method'],e['trace'],e['decision_period']) for e in events})==320
    def stat(items):
        return dict(n=len(items),merton={k:float(np.mean([e['merton'][k] for e in items])) for k in items[0]['merton']},
            residual={k:float(np.mean([e['residual'][k] for e in items])) for k in items[0]['residual']},
            paired_point_MAE_delta=float(np.mean([e['point_MAE_delta'] for e in items])),
            better=sum(e['point_MAE_delta']<0 for e in items),tied=sum(e['point_MAE_delta']==0 for e in items),worse=sum(e['point_MAE_delta']>0 for e in items))
    overall=stat(events);types={t:stat([e for e in events if e['type']==t]) for t in sorted({e['type'] for e in events})}
    methods={m:stat([e for e in events if e['source_method']==m]) for m in sorted({e['source_method'] for e in events})}
    gate=all(x['paired_point_MAE_delta']<0 for x in [overall,*types.values(),*methods.values()])
    for rel,h in frozen['source_sha256'].items():assert sha(ROOT/rel)==h,rel
    write(OUT/'events.json',events);summary=dict(events=320,original_reproduced=320,overall=overall,by_type=types,
        by_source_method=methods,development_gate_passed=gate,development_only=True,API_calls=0,training_updates=0,
        repeated_windows_and_models_not_independent=True,closed_loop_improvement_not_tested=True)
    write(OUT/'summary.json',summary);write(OUT/'completed.json',dict(status='completed',events=320,summary_sha256=sha(OUT/'summary.json'),events_sha256=sha(OUT/'events.json')))
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--register-only',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    assert args.register_only!=args.run
    if args.register_only:register()
    else:
        try:run()
        except Exception as exc:
            write(OUT/'failed.json',dict(failure=type(exc).__name__,detail=str(exc)[:500],API_calls=0,raw_outputs_preserved=True));raise
