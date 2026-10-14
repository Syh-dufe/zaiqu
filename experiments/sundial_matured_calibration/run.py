"""One fixed adjustment: cached diagnosis and small new-path prediction validation."""
import hashlib,importlib.util,json,math,sys,time,traceback
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=ROOT/'results/sundial_matured_calibration/v1'
from calibration import MaturedCalibration
from score import METHODS,score,aggregate
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def trace_hash(v):return hashlib.sha256(json.dumps(list(v[:200]),separators=(',',':')).encode()).hexdigest()
locked=module('calibration_locked_runner',ROOT/'experiments/sundial_closed_loop_development/runner.py')

def verify_freeze():
 for p,sha in read(OUT/'freeze.json')['sha256'].items():assert digest(p)==sha,p

def replay():
 rows=[];scoring=[];audits=[];windows=[]
 for seed in (11,12):
  directory=ROOT/f'results/sundial_closed_loop_development/development_v2/runs/batch01_seed{seed}'
  data=read(directory/'demands.json');scores=read(directory/'scores.json');lookup={(r['group'],r['trace'],r['decision_period']):r for r in scores}
  for trace,event in enumerate(data['events']):
   state=MaturedCalibration()
   for r in sorted([r for r in scores if r['group']=='adapted_sundial' and r['trace']==trace],key=lambda r:r['decision_period']):
    assert not r.get('execution_failure');a=r['forecast_audit'];pred=a['prediction'];p=r['decision_period'];pid=f'cached_seed{seed}_trace{trace}';wid=f'{pid}_p{p}'
    base=np.asarray(pred['selected_blocks']);adjusted,audit=state.correct(pred['block_history'],base,a['report_age'],p)
    allocation=locked.predictor.allocate(adjusted,a['report_age'],a['horizon'],a['stream_identity']);methods={}
    for name,group in [('merton','original_merton'),('naive','center_naive'),('sundial','native_sundial'),('adapted','adapted_sundial')]:
     record=lookup[group,trace,p];methods[name]=record['forecasts'][0]+record['forecasts'][1]
    methods['calibrated']=allocation['deployment'];labels=data['shock'][trace][p-1:p-1+a['horizon']]
    part,values=score(wid,pid,event['type'],methods,labels);rows.extend(part);scoring.extend(values)
    audits.append(dict(window_id=wid,path_id=pid,block_history=pred['block_history'],base_blocks=base.tolist(),adjusted_blocks=adjusted.tolist(),calibration=audit,
      identity=a['stream_identity'],horizon=a['horizon'],age=a['report_age'],paths=allocation['paths']))
    windows.append(dict(window_id=wid,path_id=pid,type=event['type'],decision_period=p,report_age=a['report_age'],block_history=pred['block_history'],future_label=labels))
 result=aggregate(rows);write(OUT/'cached_metrics.json',result);write(OUT/'cached_scoring.json',scoring);write(OUT/'cached_audits.json',audits);write(OUT/'cached_windows.json',windows)
 print('CACHED_CAUSAL_REPLAY',len(windows),result['overall'],flush=True)

def new_inputs():
 prior=module('calibration_history_common',ROOT/'experiments/sundial_adapter_development/common.py');used=prior.historical()
 for path in [ROOT/'results/sundial_adapter_development/v1/development_inputs.json',ROOT/'results/sundial_adapter_development/v1/test_inputs.json']:
  for data in read(path):
   for s in ('base','shock'):used.update(trace_hash(t) for t in data[s])
 for data in read(ROOT/'results/sundial_scenario_development/v1/inputs.json'):
  for s in ('base','shock'):used.update(trace_hash(t) for t in data[s])
 write(OUT/'historical.json',dict(consumed_hashes=sorted(used)))
 generator=module('calibration_locked_generator',ROOT/'experiments/joint_baseline_confirmation/batch.py');inputs=[];attempts=[];batch=0
 for seed in range(20272101,20272151):
  rng=np.random.default_rng(seed);items=[];seen=set();collision=False
  for trace,kind in enumerate(generator.PROFILES):
   base=np.clip(rng.poisson(10,200),0,20).astype(int).tolist();shock,event=generator.profile_trace(base,kind,-10+2*batch);pair={trace_hash(base),trace_hash(shock)}
   if pair&used or pair&seen:collision=True
   seen.update(pair);items.append(dict(path_id=f'fresh_b{batch+1}_t{trace}',seed=seed,type=kind,trace=trace,base=[base],shock=[shock],event=event))
  attempts.append(dict(seed=seed,collision=collision))
  if collision:continue
  used.update(seen);inputs.extend(items);batch+=1
  if batch==3:break
 assert len(inputs)==12;write(OUT/'validation_inputs.json',inputs);write(OUT/'generation_attempts.json',attempts)
 return inputs

def validation():
 verify_freeze();write(OUT/'validation_registration.json',dict(before_first_input_generation=True,source_freeze_sha256=digest(OUT/'freeze.json'),api=0))
 inputs=new_inputs();rows=[];scoring=[];audits=[];windows=[];predictions=[];before=locked.predictor.parameter_hash();started=time.perf_counter()
 reports=module('calibration_causal_reports',ROOT/'experiments/deepseek_refinement/reports.py')
 for item in inputs:
  state=MaturedCalibration();predictor=locked.predictor.Centers();values=item['shock'][0]
  for offset in range(0,71,5):
   p=item['event']['start_index']+3+offset;report=reports.DemandReports(3)
   for i,v in enumerate(values[:p-1],1):report.observe(v,i)
   history=report.delivered_history;blocks=[r['demand_mean'] for r in report.deliveries];age=report.age;sid=f"matured-validation|{item['path_id']}|p{p}";wid=f"{item['path_id']}_p{p}"
   old,pred=predictor.forecast(history,age,20,sid,True);base=np.asarray(pred['selected_blocks']);adjusted,audit=state.correct(blocks,base,age,p)
   calibrated=locked.predictor.allocate(adjusted,age,20,sid);native=locked.predictor.allocate(np.clip(np.asarray(pred['raw_blocks']),0,20),age,20,sid)
   merton=locked.original.forecasts(history,item['trace'],p-1,'merton',age);naive=locked.paths.generate([blocks[-1]]*20,blocks[-1],age,sid)
   methods=dict(merton=merton[0]+merton[1],naive=naive['deployment'],sundial=native['deployment'],adapted=old['deployment'],calibrated=calibrated['deployment']);labels=values[p-1:p+19]
   part,raw=score(wid,item['path_id'],item['type'],methods,labels);rows.extend(part);scoring.extend(raw)
   audits.append(dict(window_id=wid,path_id=item['path_id'],block_history=blocks,base_blocks=base.tolist(),adjusted_blocks=adjusted.tolist(),calibration=audit,
     identity=sid,horizon=20,age=age,paths=calibrated['paths']))
   predictions.append(dict(window_id=wid,prediction=pred))
   windows.append(dict(window_id=wid,path_id=item['path_id'],type=item['type'],decision_period=p,report_age=age,block_history=blocks,future_label=labels))
  write(OUT/'validation_predictions.json',predictions);print('NEW_CALIBRATION_PATH',item['path_id'],flush=True)
 assert len(windows)==180 and locked.predictor.parameter_hash()==before
 result=aggregate(rows);a=result['overall']['calibrated'];old=result['overall']['adapted'];s=result['by_type']['sustained_surge'];double=result['by_type']['double_surge']
 gate=a['crps']<old['crps'] and s['calibrated']['mae']<s['adapted']['mae'] and abs(s['calibrated']['bias'])<abs(s['adapted']['bias']) and not any(v['calibrated']['crps']>v['adapted']['crps'] and v['calibrated']['mae']>v['adapted']['mae'] for v in result['by_type'].values()) and double['calibrated']['crps']<=double['adapted']['crps']
 result['fixed_gate_passed']=bool(gate);write(OUT/'validation_metrics.json',result);write(OUT/'validation_scoring.json',scoring);write(OUT/'validation_audits.json',audits);write(OUT/'validation_windows.json',windows)
 write(OUT/'model_checks.json',dict(before=before,after=before,unchanged=True,wall_seconds=time.perf_counter()-started));verify_freeze()
 write(OUT/'completed.json',dict(api=0,model_updates=0,cached_windows=len(read(OUT/'cached_windows.json')),new_paths=12,new_windows=180,fixed_gate_passed=bool(gate),inventory_cost_test=False))
 print('MATURED_CALIBRATION_VALIDATION',result['overall'],result['by_type']['sustained_surge'],bool(gate),flush=True)

def main():
 assert not OUT.exists(),'Preserve previous attempt'
 old=ROOT/'results/sundial_closed_loop_development/development_v2';assert read(old/'user_stopped.json')['status']=='stopped_by_user'
 f=read(old/'freeze.json');hashes={str(ROOT/p):s for p,s in f['source_sha256'].items()};hashes.update(f['dependencies'])
 files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/specs/2026-10-14-sundial-matured-calibration-design.md',ROOT/'docs/superpowers/plans/2026-10-14-sundial-matured-calibration.md',locked.predictor.ADAPTER,old/'user_stopped.json']
 for seed in (11,12):
  directory=old/f'runs/batch01_seed{seed}';assert read(directory/'audit.json')['status']=='passed';files.extend(p for p in directory.glob('*') if p.is_file())
 hashes.update({str(p):digest(p) for p in files})
 for p,sha in hashes.items():assert digest(p)==sha,p
 OUT.mkdir(parents=True);(OUT/'started.lock').write_text('one fixed no-API calibration attempt',encoding='utf-8')
 write(OUT/'freeze.json',dict(sha256=hashes,api=0,training=0,before_generation=True,parameters=dict(half_factor=.5,error_clip=6,max_shift=3,last_matured_errors=3,max_report_age=6)))
 replay();validation()

if __name__=='__main__':
 try:main()
 except Exception as e:
  if OUT.exists():write(OUT/'failed.json',dict(error=type(e).__name__,detail=str(e),preserved=True,api=0))
  traceback.print_exc();raise
