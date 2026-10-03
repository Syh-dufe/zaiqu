"""Finish all preregistered cache replays; no new model requests."""
import csv
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def main():
    out=ROOT/'results/deepseek_refinement/predictor_merton_diagnosis'
    if out.exists():raise SystemExit('Refuse overwrite')
    out.mkdir(parents=True)
    progress=dict(status='running',batches=[])
    save=lambda:(out/'progress.json').write_text(json.dumps(progress,indent=2),encoding='utf-8')
    save()
    for i in range(4):
        name=f'flash_predictor_merton_replay_batch{i+1}';p=out.parent/name
        if p.exists():
            if not (p/'completed.json').exists():raise SystemExit('Existing incomplete/running replay; diagnose before resuming')
        else:
            cmd=[sys.executable,'-u',str(Path(__file__).with_name('run.py')),'--run-name',name,'--cases','4',
                 '--demand-seed',str(20261044+2*i),'--event-seed',str(20261045+2*i),
                 '--correction-periods','5','--refinement-schedule','observed','--single-only','--predictor','merton',
                 '--replay-calls',str(out.parent/f'flash_confirm_single_v3_batch{i+1}'/'calls.json')]
            with (out/f'{name}.log').open('w',encoding='utf-8') as f:
                result=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
            if result.returncode:progress['status']='failed';save();raise SystemExit(result.returncode)
        progress['batches'].append(name);save();print('COMPLETED',name,flush=True)
    combined=[];errors={k:[] for k in ('merton','residual')}
    for i in range(4):
        p=out.parent/f'flash_predictor_merton_replay_batch{i+1}';original=out.parent/f'flash_confirm_single_v3_batch{i+1}'
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('summarize.py')),str(p)],cwd=ROOT,capture_output=True,text=True)
        if result.returncode:raise SystemExit(result.stderr)
        source=json.loads((original/'demands.json').read_text());current=json.loads((p/'demands.json').read_text());assert source==current
        calls=json.loads((p/'calls.json').read_text());assert len(calls)==4 and all(c['replayed'] for c in calls)
        assert json.loads((p/'summary.json').read_text())['api_calls']==0
        for method,directory in (('merton',p),('residual',original)):
            episodes=json.loads((directory/'episodes.json').read_text())
            for e in episodes:
                if e['scenario']=='shock':combined.append(dict(method=method,batch=i,**e))
            prediction=list(csv.DictReader((directory/'prediction_errors.csv').open()))
            errors[method].extend(float(r['mean_absolute_error']) for r in prediction if r['group']=='llm_single')
    import numpy as np
    mean={}
    for method in errors:
        mean[method]={}
        for group in ('happo','manual_screen','llm_single'):
            rs=[r for r in combined if r['method']==method and r['group']==group];assert len(rs)==16
            mean[method][group]=dict(cost=float(np.mean([r['cost'] for r in rs])),backlog=float(np.mean([r['downstream_backlog'] for r in rs])))
    result=dict(means=mean,prediction_mae={k:float(np.mean(v)) for k,v in errors.items()},new_api_calls=0,
                scope='Paired development diagnosis on all16 previously observed cases, same causal initial responses, not independent validation')
    (out/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    progress['status']='completed';save();print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
