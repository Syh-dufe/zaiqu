import sys, math, traceback
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/sundial_adapter_development'))
import common as c
import forecast
from adapter import features,transform
from evaluate import crps
OLD=c.OUT
OUT=ROOT/'results/sundial_scenario_development/v1'

def main():
 c.verify_freeze()
 fit=c.read(OLD/'fit_completed.json');assert c.digest(OLD/'best_adapter.json')==fit['best_sha256']
 assert not OUT.exists(),'Preserve prior attempt'
 OUT.mkdir(parents=True);(OUT/'started.lock').write_text('one attempt',encoding='utf-8')
 hashes=c.read(OLD/'freeze.json')['sha256'].copy()
 for p in [Path(__file__),ROOT/'docs/superpowers/specs/2026-10-14-sundial-scenarios-design.md',ROOT/'docs/superpowers/plans/2026-10-14-sundial-scenarios.md',OLD/'best_adapter.json']:
  hashes[str(p)]=c.digest(p)
 c.write(OUT/'freeze.json',dict(sha256=hashes,api=0,adapter_sha256=fit['best_sha256'],before_generation=True))
 used=c.historical()
 for phase in ('development','test'):
  for item in c.read(OLD/f'{phase}_inputs.json'):
   for key in ('base','shock'):used.update(c.trace_hash(t) for t in item[key])
 c.write(OUT/'historical.json',dict(consumed_hashes=sorted(used)))
 generator=c.module('scenario_shock_generator',ROOT/'experiments/joint_baseline_confirmation/batch.py')
 reports=c.module('scenario_reports',ROOT/'experiments/deepseek_refinement/reports.py')
 inputs=[];cases=[];attempts=[];seed=20272001
 for bg in ('stationary','trend','periodic'):
  for profile in generator.PROFILES:
   for rep in range(5):
    while True:
     rng=np.random.default_rng(seed);t=np.arange(200)
     mean=np.full(200,10.) if bg=='stationary' else 6+8*t/199 if bg=='trend' else 10+4*np.sin(2*np.pi*t/40)
     base=np.clip(rng.poisson(mean),0,20).astype(int).tolist()
     shock,event=generator.profile_trace(base,profile,-10+2*rep)
     pair={c.trace_hash(base),c.trace_hash(shock)};collision=bool(pair&used)
     attempts.append(dict(seed=seed,collision=collision));seed+=1
     if not collision:break
    used.update(pair);pid=f'{bg}_{profile}_{rep+1}'
    inputs.append(dict(path_id=pid,background=bg,type=profile,seed=seed-1,base=[base],shock=[shock],event=event,mean=mean.tolist()))
    for offset in (0,5,10,15,25,40):
     p=event['start_index']+3+offset;r=reports.DemandReports(3)
     for i,v in enumerate(shock[:p-1],1):r.observe(v,i)
     blocks=[d['demand_mean'] for d in r.deliveries]
     assert len(blocks)*3+r.age==p-1
     cases.append(dict(id=f'{pid}_o{offset}',path_id=pid,background=bg,type=profile,offset=offset,decision_period=p,report_age=r.age,block_history=blocks,future_label=shock[p-1:p+19]))
 c.write(OUT/'inputs.json',inputs);c.write(OUT/'generation_log.json',attempts)
 c.write(OUT/'test_cases.json',cases);c.write(OUT/'test_prepared.json',dict(cases_sha256=c.digest(OUT/'test_cases.json'),input_sha256=c.digest(OUT/'inputs.json'),paths=60,cases=360))
 c.OUT=OUT;forecast.OUT=OUT
 forecast.run('test')
 pred={r['case_id']:r for r in c.read(OUT/'test_predictions.json')};weights=c.read(OLD/'best_adapter.json')['weights'];rows=[];scoring=[]
 for case in cases:
  p=pred[case['id']];s=np.asarray(p['blocks']);a=transform(s,features(case['block_history'],s,case['report_age']),weights)
  age=case['report_age'];starts=[j for j in range(-age,20,3) if 0<=j and j+3<=20];idx=[(j+age)//3 for j in starts]
  y=np.asarray([np.mean(case['future_label'][j:j+3]) for j in starts]);methods=dict(sundial=s[:,idx],adapted=a[:,idx])
  for m in ('merton','naive'):
   v=np.asarray(p[m]['paths']);methods[m]=np.stack([v[:,j:j+3].mean(axis=1) for j in starts],axis=1)
  for m,x in methods.items():
   score=crps(x,y);mae=float(np.abs(x.mean(axis=0)-y).mean())
   # Independent sorted-sample identity, no pairwise scoring implementation reuse.
   n=len(x);sorted_x=np.sort(x,axis=0);check=float(np.mean(np.abs(x-y).mean(axis=0)-((2*np.arange(1,n+1)-n-1)[:,None]*sorted_x).sum(axis=0)/n**2))
   assert abs(score-check)<1e-10
   rows.append(dict(case_id=case['id'],path_id=case['path_id'],background=case['background'],type=case['type'],method=m,crps=score,mae=mae))
   scoring.append(dict(case_id=case['id'],method=m,samples=x.tolist(),labels=y.tolist()))
 path_rows=[]
 for item in inputs:
  local=[r for r in rows if r['path_id']==item['path_id']];assert len(local)==24
  means={m:{k:float(np.mean([r[k] for r in local if r['method']==m])) for k in ('crps','mae')} for m in methods}
  path_rows.append(dict(path_id=item['path_id'],background=item['background'],type=item['type'],means=means))
 def aggregate(ps):return {m:{k:float(np.mean([p['means'][m][k] for p in ps])) for k in ('crps','mae')} for m in methods}
 cells=[(b,t) for b in ('stationary','trend','periodic') for t in generator.PROFILES]
 diff=np.asarray([[[p['means']['adapted']['crps']-p['means'][m]['crps'] for m in ('merton','naive')] for p in path_rows if (p['background'],p['type'])==cell] for cell in cells]);assert diff.shape==(12,5,2)
 rng=np.random.default_rng(20272051);idx=rng.integers(0,5,(20000,12,5));boot=np.stack([diff[j][idx[:,j]].mean(axis=1) for j in range(12)],axis=1).mean(axis=1)
 contrasts={m:dict(mean=float(diff[:,:,j].mean()),ci_97_5=np.quantile(boot[:,j],[.0125,.9875]).tolist()) for j,m in enumerate(('merton','naive'))}
 result=dict(overall=aggregate(path_rows),by_background={b:aggregate([p for p in path_rows if p['background']==b]) for b in ('stationary','trend','periodic')},by_cell={b+'_'+t:aggregate([p for p in path_rows if p['background']==b and p['type']==t]) for b,t in cells},paths=path_rows,per_case=rows,contrasts=contrasts,bootstrap_seed=20272051,replicates=20000,exploratory=True)
 c.write(OUT/'metrics.json',result);c.write(OUT/'scoring_values.json',scoring)
 c.verify_freeze();assert c.digest(OLD/'best_adapter.json')==fit['best_sha256']
 c.write(OUT/'completed.json',dict(paths=60,windows=360,rows=len(rows),api=0,training=0,independent_sorted_crps=True,adapter_unchanged=True,input_sha256=c.digest(OUT/'inputs.json')))
 print('SCENARIO_COMPLETE',result['overall'],contrasts,flush=True)

if __name__=='__main__':
 try:main()
 except Exception as e:
  if OUT.exists():c.write(OUT/'failed.json',dict(error=type(e).__name__,detail=str(e)))
  traceback.print_exc();raise
