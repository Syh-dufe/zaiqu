"""Execute all five preregistered v3 batches before analysing performance."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]


def main():
    out=ROOT/'results/deepseek_refinement/confirmation_v3_20'
    if out.exists():raise SystemExit('Refuse overwrite; diagnose/resume explicitly instead.')
    calls=sum(len(json.loads(p.read_text(encoding='utf-8'))) for p in (ROOT/'results/deepseek_refinement').glob('*/calls.json'))
    if calls+60>120:raise SystemExit('Series API budget exceeded')
    names=[f'flash_confirm_v3_batch{i+1}' for i in range(5)]
    assert not any((out.parent/n).exists() for n in names)
    out.mkdir(parents=True)
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).with_name('run.py'),Path(__file__).with_name('shadow.py'))}
    state=dict(source_hashes=sources,calls_before=calls,batches=[],status='running',started_unix=time.time())
    def save(): (out/'progress.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
    save()
    for i,name in enumerate(names):
        command=[sys.executable,'-u',str(Path(__file__).with_name('run.py')),'--run-name',name,'--cases','4',
            '--demand-seed',str(20261030+2*i),'--event-seed',str(20261031+2*i),
            '--correction-periods','5','--refinement-schedule','observed']
        print('START',name,flush=True)
        with (out/f'{name}.log').open('w',encoding='utf-8') as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        state['batches'].append(dict(name=name,returncode=result.returncode))
        if result.returncode:
            state['status']='failed';save();raise SystemExit(result.returncode)
        save(); print('COMPLETED',name,flush=True)
    # Source audit prevents changing algorithm partway through this experiment.
    assert sources=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).with_name('run.py'),Path(__file__).with_name('shadow.py'))}
    for name in names:
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('summarize.py')),str(out.parent/name)],cwd=ROOT,capture_output=True,text=True)
        if result.returncode:
            state['status']='summary_failed';save();raise SystemExit(result.stderr)
    import numpy as np
    groups=('manual_screen','llm_single','llm_iterative')
    combined={g:[] for g in groups}; metrics={g:[] for g in ('happo',)+groups}; usage=dict(calls=0,tokens=0,api_seconds=0,wall_seconds=0)
    all_paired=[]
    for name in names:
        summary=json.loads((out.parent/name/'summary.json').read_text())
        done=json.loads((out.parent/name/'completed.json').read_text())
        assert done['episodes']==32 and all(c['unchanged'] for c in done['parameter_checks'].values())
        for p in summary['paired']:
            if p['scenario']=='shock' and p['group'] in groups:
                combined[p['group']].append([p['cost_delta'],p['backlog_delta']])
                all_paired.append(dict(batch=name,**p))
        episodes=json.loads((out.parent/name/'episodes.json').read_text())
        for e in episodes:
            if e['scenario']=='shock': metrics[e['group']].append([e['cost'],e['downstream_backlog']])
        usage['calls']+=summary['api_calls'];usage['tokens']+=summary['tokens'];usage['api_seconds']+=summary['api_seconds'];usage['wall_seconds']+=done['wall_seconds']
    rng=np.random.default_rng(20261040);indices=rng.integers(0,20,size=(20000,20));analysis={}
    for group,values in combined.items():
        arr=np.asarray(values);assert arr.shape==(20,2)
        ci=np.quantile(arr[indices].mean(axis=1),[.025,.975],axis=0)
        analysis[group]=dict(mean_delta=arr.mean(axis=0).tolist(),ci95=ci.tolist(),
            lower_cost_cases=int((arr[:,0]<0).sum()),higher_cost_cases=int((arr[:,0]>0).sum()),
            lower_backlog_cases=int((arr[:,1]<0).sum()),higher_backlog_cases=int((arr[:,1]>0).sum()),
            both_lower_cases=int(((arr[:,0]<0)&(arr[:,1]<0)).sum()),
            both_ci_upper_below_zero=bool((ci[1]<0).all()))
    report=dict(analysis=analysis,absolute_means={g:np.mean(v,axis=0).tolist() for g,v in metrics.items()},usage=usage,
        metric_order=['system_cost_per_node_period','downstream_mean_backlog'],n_demands=20,
        bootstrap='paired demand-level, seed20261040, 20000 resamples, percentile95%',
        scope='One frozen training seed, fixed simulated distribution and reliable notification. No actual disaster-data or deployment-latency verification.')
    (out/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with (out/'paired.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(all_paired[0]));w.writeheader();w.writerows(all_paired)
    state['status']='completed';state['ended_unix']=time.time();save()
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
