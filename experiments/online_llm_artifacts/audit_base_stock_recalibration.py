"""Read-only second-process reconstruction of the registered recalibration outputs."""
import csv,gzip,hashlib,importlib.util,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/base_stock_recalibration/v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 spec=importlib.util.spec_from_file_location('recalibration_scalar_only',ROOT/'experiments/online_llm_artifacts/audit_base_stock_numerical.py')
 audit=importlib.util.module_from_spec(spec);sys.modules[spec.name]=audit;spec.loader.exec_module(audit)
 reg=read(OUT/'registration.json');done=read(OUT/'completed.json');summary=read(OUT/'summary.json');scores=read(OUT/'episodes.json')
 for p,h in reg['files'].items():assert sha(Path(p))==h,p
 assert sha(OUT/'selection.json')==done['selection_sha256']
 lookup={(x['stage'],x['z'],x['batch'],x['trace'],x['scenario']):x for x in scores};assert len(lookup)==len(scores)==done['episodes']
 inputs={(x['split'],x['batch']):read(Path(x['path'])) for x in reg['inputs']}
 fixed=read(ROOT/'results/submission_required/v1/inputs/confirmation01_main.json')
 counted=0;seen=set()
 for p in (OUT/'runs').rglob('periods.csv.gz'):
  with gzip.open(p,'rt',encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
  assert len(rows)==3600
  groups={}
  for row in rows:
   key=(row['stage'],int(row['z']),int(row['batch']),int(row['trace']),row['scenario']);groups.setdefault(key,[]).append(row)
  assert len(groups)==6
  for key,values in groups.items():
   stage,z,batch,trace,scenario=key;assert key not in seen;seen.add(key)
   data=fixed if stage=='fixed' else inputs[stage,batch]
   assert len({(int(x['period']),int(x['node'])) for x in values})==600
   cost=audit.verify_episode(values,data[scenario][trace],dict(name=f'{stage}_z{z}',z=z,information='local',rounding='ceil'))
   assert abs(cost-lookup[key]['cost'])<1e-10
   assert abs(statistics.mean(float(x['backlog']) for x in values if int(x['node'])==0)-lookup[key]['downstream_backlog'])<1e-10
   counted+=len(values)
 assert seen==set(lookup) and counted==done['rows']
 dev=[dict(z=z,shock_cost=statistics.mean(x['cost'] for x in scores if x['stage']=='development' and x['z']==z and x['scenario']=='shock')) for z in range(20)]
 selected=min(dev,key=lambda x:(x['shock_cost'],x['z']))['z'];assert selected==summary['selected_z']
 for x,y in zip(dev,summary['development_scan']):assert x['z']==y['z'] and abs(x['shock_cost']-y['shock_cost'])<1e-10
 for z,value in summary['holdout'].items():
  local=[x for x in scores if x['stage']=='holdout' and x['z']==int(z) and x['scenario']=='shock']
  assert len(local)==30 and abs(statistics.mean(x['cost'] for x in local)-value['shock_cost'])<1e-10
  for kind,cost in value['by_type'].items():assert abs(statistics.mean(x['cost'] for x in local if x['type']==kind)-cost)<1e-10
 original=read(ROOT/'results/sundial_fixed_base_stock/v2/summary.json')
 fixed_scores=read(OUT/'fixed_episodes_including_reused.json')
 for row in summary['fixed_by_type']:
  old=next(x for x in original['by_type'] if x['type']==row['type'])
  for method in ('happo','full_merton','full_sundial'):assert row[method]==old[method]
  for label,z in [('base_stock_selected',selected),('base_stock_reference8',8),('base_stock_historical2',2)]:
   value=next(x for x in fixed_scores if x['z']==z and x['type']==row['type'] and x['scenario']=='shock');assert value['cost']==row[label]
 for label,cost in summary['fixed_overall'].items():assert abs(statistics.mean(x[label] for x in summary['fixed_by_type'])-cost)<1e-10
 archived=read(ROOT/'docs/artifacts/base_stock_recalibration_completed_v1/manifest.json')
 for p,item in archived['files'].items():assert hashlib.sha256(gzip.decompress((ROOT/p).read_bytes())).hexdigest()==item['source_sha256']
 result=dict(status='passed',new_episodes=len(scores),new_node_periods=counted,selected_z=selected,source_hashes_checked=len(reg['files']),raw_state_cost_action_reconstructed=True,selection_and_summary_recomputed=True,archived_files_checked=len(archived['files']),numerical_boundary_count=len(audit.BOUNDARIES),numerical_boundaries=audit.BOUNDARIES,api=0)
 with (OUT/'independent_audit.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 print(json.dumps({k:v for k,v in result.items() if k!='numerical_boundaries'}))
if __name__=='__main__':main()
