"""Fixed 48-case point-forecast pilot. No API or ordering-policy changes."""
import argparse
import csv
import hashlib
import json
import math
import sys
import time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
OUT=ROOT/'results/timesfm_forecast_pilot/development_v1'
DEPS=Path('C:/Users/13384/.cache/zaiqu-timesfm-pilot/deps')
REVISION='1d952420fba87f3c6dee4f240de0f1a0fbc790e3'
MODEL=Path('C:/Users/13384/.cache/zaiqu-timesfm-pilot/model')/REVISION
sys.path.insert(0,str(ROOT/'experiments/deepseek_refinement'))
from reports import DemandReports
from shadow import forecasts

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        while b:=f.read(8*1024*1024):h.update(b)
    return h.hexdigest()

def prepare():
    assert not OUT.exists(),'Preserve existing pilot output'
    OUT.mkdir(parents=True)
    cases=[];inputs={}
    for batch in (1,6):
        path=ROOT/f'results/online_llm_guard_pool/development_v1/runs/development_batch{batch:02d}_seed11/demands.json'
        data=read(path);inputs[str(path)]=digest(path)
        for trace,event in enumerate(data['events']):
            for offset in (0,5,10,15,25,40):
                p=event['start_index']+3+offset
                report=DemandReports(3)
                for index,value in enumerate(data['shock'][trace][:p-1],start=1):report.observe(value,index)
                blocks=[r['demand_mean'] for r in report.deliveries]
                assert len(blocks)*3==len(report.delivered_history)
                assert all(r['available_from_decision_period']<=p for r in report.deliveries)
                assert report.age in (0,1,2)
                future=data['shock'][trace][p-1:p+19]
                assert len(future)==20 and len(blocks)>=2
                cases.append(dict(id=f'b{batch}_t{trace}_offset{offset}',batch=batch,trace=trace,type=event['type'],offset=offset,decision_period=p,report_age=report.age,block_history=blocks,reconstructed_history=report.delivered_history,future_label=future))
    assert len(cases)==48 and len({c['id'] for c in cases})==48
    write(OUT/'cases.json',cases)
    write(OUT/'prepared.json',dict(cases=48,paths=8,inputs_sha256=inputs,api=0,training=0))
    print('PREPARED_48_CAUSAL_INPUTS',flush=True)

def extrapolate(blocks,count):
    y=np.asarray(blocks[-5:],dtype=float);x=np.arange(len(y),dtype=float)
    slope=float(np.dot(x-x.mean(),y-y.mean())/np.dot(x-x.mean(),x-x.mean()))
    return np.clip(y.mean()+slope*(np.arange(len(y),len(y)+count)-x.mean()),0,20)

def align(blocks,age):
    values=np.repeat(np.asarray(blocks,dtype=float),3)[age:age+20]
    assert len(values)==20
    return np.clip(values,0,20)

def run():
    assert not (OUT/'started.lock').exists(),'Do not repeat pilot'
    setup=read(ROOT/'results/timesfm_forecast_pilot/setup_v1/download_completed.json')
    assert setup['revision']==REVISION
    model_path=MODEL/'model.safetensors'
    assert digest(model_path)==setup['files']['model.safetensors']['sha256']
    hashes=read(OUT/'prepared.json')['inputs_sha256'].copy()
    source_files=list(HERE.glob('*.py'))+[ROOT/'experiments/deepseek_refinement/shadow.py',ROOT/'experiments/deepseek_refinement/reports.py',ROOT/'experiments/deepseek_pilot/rules.py',ROOT/'docs/superpowers/specs/2026-10-14-timesfm-pilot-design.md',ROOT/'docs/superpowers/plans/2026-10-14-timesfm-pilot.md',OUT/'cases.json',model_path,MODEL/'config.json']
    source_files+=list(DEPS.rglob('*.py'))
    for p in source_files:hashes[str(p)]=digest(p)
    dependencies={p.parent.name:digest(p) for p in DEPS.glob('*.dist-info/METADATA')}
    write(OUT/'freeze.json',dict(sha256=hashes,dependency_metadata_sha256=dependencies,revision=REVISION,timesfm_version='2.0.2',checkpoint='2.5-200m',cpu_only=True,torch_compile=False,report_block_input=True))
    (OUT/'started.lock').write_text('one registered attempt\n',encoding='utf-8')
    cases=read(OUT/'cases.json')
    sys.path.insert(0,str(DEPS))
    import torch
    from timesfm import ForecastConfig
    from timesfm.timesfm_2p5.timesfm_2p5_torch import TimesFM_2p5_200M_torch
    torch.set_num_threads(2);torch.manual_seed(20261014)
    assert not torch.cuda.is_available(),'Pilot registered as CPU-only'
    started=time.perf_counter()
    model=TimesFM_2p5_200M_torch(torch_compile=False)
    model.load_checkpoint(str(model_path),torch_compile=False)
    model.compile(ForecastConfig(max_context=128,max_horizon=32,per_core_batch_size=4))
    write(OUT/'model_loaded.json',dict(seconds=time.perf_counter()-started,forecast_config=str(model.forecast_config),parameter_count=sum(p.numel() for p in model.model.parameters())))
    predictions=[];times=[]
    for start in range(0,len(cases),4):
        batch=cases[start:start+4]
        before=time.perf_counter()
        with torch.inference_mode():points,quantiles=model.forecast(horizon=8,inputs=[np.asarray(c['block_history'],dtype=float) for c in batch])
        elapsed=time.perf_counter()-before;times.append(elapsed)
        assert points.shape==(len(batch),8) and np.isfinite(points).all()
        for index,c in enumerate(batch):
            base_forecast=forecasts(c['reconstructed_history'],c['trace'],c['decision_period']-1,'merton',c['report_age'])
            merton=np.asarray(base_forecast[0]+base_forecast[1],dtype=float).mean(axis=0)
            count=math.ceil((c['report_age']+20)/3)
            values={'merton':merton,'trend':align(extrapolate(c['block_history'],count),c['report_age']),
                    'naive':np.full(20,c['block_history'][-1]),'timesfm':align(points[index],c['report_age'])}
            predictions.append(dict(case_id=c['id'],methods={m:v.tolist() for m,v in values.items()},timesfm_raw_blocks=points[index].tolist(),timesfm_raw_quantiles=quantiles[index].tolist(),merton_paths=base_forecast,batch_inference_seconds=elapsed))
        write(OUT/'predictions.json',predictions)
        write(OUT/'progress.json',dict(status='running',completed=len(predictions),target=48,api=0))
        print('FORECASTED',len(predictions),48,flush=True)
    for p,h in hashes.items():assert digest(p)==h,'Frozen source/input/model changed'
    write(OUT/'run_finished.json',dict(cases=48,api=0,training=0,model_unchanged=True,source_hashes_unchanged=True,inference_seconds=sum(times),elapsed_seconds=time.perf_counter()-started))
    print('ALL48_FINISHED',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--run',action='store_true');opts=parser.parse_args()
    try:
        if opts.prepare:prepare()
        elif opts.run:run()
        else:raise ValueError('Choose prepare or run')
    except Exception as exc:
        if OUT.exists():write(OUT/'failed.json',dict(error=type(exc).__name__,detail=str(exc)))
        raise
