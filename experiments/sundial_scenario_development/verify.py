"""Read-only independent recomputation; does not import scenario runner/scorer."""
import hashlib,json,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_scenario_development/v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
trace_hash=lambda v:hashlib.sha256(json.dumps(v,separators=(',',':')).encode()).hexdigest()
done=read(OUT/'completed.json');assert done['rows']==1440
for p,sha in read(OUT/'freeze.json')['sha256'].items():assert digest(Path(p))==sha,p
hist=set(read(OUT/'historical.json')['consumed_hashes']);seen=set();inputs={r['path_id']:r for r in read(OUT/'inputs.json')}
for item in inputs.values():
 t=np.arange(200);bg=item['background'];mean=np.full(200,10.) if bg=='stationary' else 6+8*t/199 if bg=='trend' else 10+4*np.sin(2*np.pi*t/40)
 base=np.clip(np.random.default_rng(item['seed']).poisson(mean),0,20).astype(int).tolist();assert base==item['base'][0]
 shock=base.copy()
 for interval in item['event']['intervals']:
  for j in range(interval['start'],interval['end']):
   f=interval['factor'];shock[j]=min(20,math.ceil(base[j]*f)) if f>1 else math.floor(base[j]*f)
 assert shock==item['shock'][0]
 pair={trace_hash(base),trace_hash(shock)};assert not pair&hist and not pair&seen;seen.update(pair)
cases={c['id']:c for c in read(OUT/'test_cases.json')}
for c in cases.values():
 v=inputs[c['path_id']]['shock'][0];n=c['decision_period']-1
 blocks=[sum(v[j:j+3])/3 for j in range(0,n-n%3,3)]
 assert np.allclose(blocks,c['block_history'],rtol=0,atol=1e-12) and c['report_age']==n%3
 assert c['future_label']==v[n:n+20]
m=read(OUT/'metrics.json');score_lookup={(r['case_id'],r['method']):r for r in m['per_case']};maximum=0
for r in read(OUT/'scoring_values.json'):
 xs=np.asarray(r['samples']);ys=np.asarray(r['labels']);n=len(xs);values=[]
 for j,y in enumerate(ys):
  x=sorted(xs[:,j]);values.append(sum(abs(v-y) for v in x)/n-sum((2*k-n-1)*v for k,v in enumerate(x,1))/n**2)
 score=float(np.mean(values));mae=float(np.mean([abs(sum(xs[:,j])/n-y) for j,y in enumerate(ys)]));stored=score_lookup[r['case_id'],r['method']]
 maximum=max(maximum,abs(score-stored['crps']),abs(mae-stored['mae']));assert maximum<1e-10
for p in m['paths']:
 for method,values in p['means'].items():
  local=[r for r in m['per_case'] if r['path_id']==p['path_id'] and r['method']==method];assert len(local)==6
  for k in ('crps','mae'):assert abs(np.mean([r[k] for r in local])-values[k])<1e-12
model=read(OUT/'test_forecast_completed.json');assert model['model_before']==model['model_after'] and model['cases']==360
cells=[(b,t) for b in ('stationary','trend','periodic') for t in ('single_surge','sustained_surge','double_surge','surge_then_drop')]
diff=np.asarray([[[p['means']['adapted']['crps']-p['means'][method]['crps'] for method in ('merton','naive')] for p in m['paths'] if (p['background'],p['type'])==cell] for cell in cells])
rng=np.random.default_rng(20272051);samples=[]
for _ in range(20000):
 idx=rng.integers(0,5,(12,5));samples.append(np.mean([np.mean(diff[j][idx[j]],axis=0) for j in range(12)],axis=0))
for i,method in enumerate(('merton','naive')):
 assert np.allclose(np.quantile(np.asarray(samples)[:,i],[.0125,.9875]),m['contrasts'][method]['ci_97_5'],rtol=0,atol=1e-12)
record=dict(paths=60,windows=360,method_rows=1440,raw_demand_reconstruction=True,causal_reports=True,history_collision_free=True,scalar_metrics_max_error=maximum,independent_bootstrap=True,source_and_adapter_hashes=True,model_unchanged=True,api=0)
(OUT/'independent_verification.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print('INDEPENDENT_SCENARIO_AUDIT',record)
