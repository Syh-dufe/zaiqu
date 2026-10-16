"""Registered zero-history sensitivity; frozen default-ten baseline is retained."""
import argparse,csv,gzip,importlib.util,json,os,socket,statistics,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=ROOT/'results/base_stock_zero_history/v1'
SPEC=ROOT/'docs/superpowers/specs/2026-10-16-base-stock-zero-history-design.md'
PLAN=ROOT/'docs/superpowers/plans/2026-10-16-base-stock-zero-history.md'
s=importlib.util.spec_from_file_location('zero_history_registered_reference',ROOT/'experiments/base_stock_recalibration/batch.py');ref=importlib.util.module_from_spec(s);sys.modules[s.name]=ref;s.loader.exec_module(ref)
old=ref.old;read=old.read;write=old.write;sha=old.sha;ZS=(2,3,8)
def verify():
 v=read(OUT/'registration.json')
 for p,h in v['files'].items():assert sha(Path(p))==h,p
 return v
def register():
 assert not OUT.exists();OUT.mkdir(parents=True)
 files=dict(read(ref.OUT/'registration.json')['files'])
 for p in [HERE/'batch.py',SPEC,PLAN,ref.OUT/'summary.json',ref.OUT/'fixed_episodes_including_reused.json',ref.OUT/'completed.json',ref.OUT/'registration.json',ROOT/'experiments/base_stock_recalibration/batch.py']:
  files[str(p)]=sha(p)
 write(OUT/'registration.json',dict(files=files,input=str(old.INPUT),z=list(ZS),initial_history=[0]*40,episodes=18,node_periods=10800,api=0,retune=False,posthoc_sensitivity=True,created=time.time()))
 public=ref.reuse.archive(ROOT/'docs/artifacts/base_stock_zero_history_preregistration_v1',[HERE/'batch.py',SPEC,PLAN,OUT/'registration.json'])
 write(OUT/'publication.json',dict(files=public));print('ZERO_HISTORY_REGISTERED',flush=True)
def ten_cost(z,kind,scenario):
 values=read(ref.OUT/'fixed_episodes_including_reused.json')
 return next(x['cost'] for x in values if x['z']==z and x['type']==kind and x['scenario']==scenario)
def run():
 reg=verify();old.check_publication(OUT/'publication.json')
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert head==remote
 with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),revision=head,started=time.time(),api=0));start=time.perf_counter()
 def forbidden(*a,**kw):raise RuntimeError('Network disabled in local sensitivity')
 socket.socket.connect=forbidden;socket.create_connection=forbidden
 try:
  data=read(old.INPUT);scores=[]
  for z in ZS:
   for trace,kind in enumerate(old.KINDS):
    prefix=None
    for scenario in ('base','shock'):
     verify();write(OUT/'progress.json',dict(status='running',z=z,type=kind,scenario=scenario,completed_episodes=len(scores),api=0))
     result=old.bs.episode(data[scenario][trace],z=z,information='local',rounding='ceil',initial_history=[0]*40);rows=result.pop('rows')
     config=dict(name=f'z{z}_zero_history',z=z,information='local',rounding='ceil',initial_history=[0]*40)
     cost=old.numerical.verify_episode(rows,data[scenario][trace],config);assert abs(cost-result['cost'])<1e-10 and result['ledger_verified']
     if scenario=='base':prefix=rows
     else:
      for a,b in zip(prefix,rows):
       if int(b['period'])>=data['events'][trace]['start_index']:break
       assert a==b
     path=OUT/'runs'/f'z{z}'/f'{kind}_{scenario}.csv.gz';path.parent.mkdir(parents=True,exist_ok=True)
     with gzip.open(path,'xt',encoding='utf-8',newline='') as f:
      w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
     scores.append(dict(z=z,trace=trace,type=kind,scenario=scenario,path=str(path),initial_history_value=0,**result));write(OUT/'episodes.json',scores)
  table=[]
  for z in ZS:
   for kind in old.KINDS:
    zero=next(x['cost'] for x in scores if x['z']==z and x['type']==kind and x['scenario']=='shock');ten=ten_cost(z,kind,'shock')
    table.append(dict(z=z,type=kind,history0=zero,history10=ten,change_percent=100*(zero/ten-1)))
  overall={str(z):dict(history0=statistics.mean(x['history0'] for x in table if x['z']==z),history10=statistics.mean(x['history10'] for x in table if x['z']==z)) for z in ZS}
  write(OUT/'summary.json',dict(by_type=table,overall=overall,api=0,episodes=18,only_initial_history_changed=True,no_retune=True,standard_ten_retained=True))
  write(OUT/'numerical_boundaries.json',old.numerical.BOUNDARIES);verify();assert len(scores)==18
  write(OUT/'completed.json',dict(episodes=18,rows=10800,api=0,seconds=time.perf_counter()-start,scalar_audit_passed=True));write(OUT/'progress.json',dict(status='completed',episodes=18,api=0))
  public=ref.reuse.archive(ROOT/'docs/artifacts/base_stock_zero_history_completed_v1',[p for p in OUT.rglob('*') if p.is_file()]+[HERE/'batch.py',SPEC,PLAN]);write(OUT/'completed_publication.json',dict(files=public));print('ZERO_HISTORY_COMPLETED',overall,flush=True)
 except Exception as e:write(OUT/'failed.json',dict(error=type(e).__name__,detail=str(e),preserved=True,api=0));traceback.print_exc();raise
def audit():
 verify();scores=read(OUT/'episodes.json');data=read(old.INPUT);count=0
 for e in scores:
  with gzip.open(e['path'],'rt',encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
  cost=old.numerical.verify_episode(rows,data[e['scenario']][e['trace']],dict(name=f"z{e['z']}_zero",z=e['z'],initial_history=[0]*40))
  assert abs(cost-e['cost'])<1e-10;count+=len(rows)
 summary=read(OUT/'summary.json')
 for line in summary['by_type']:
  assert abs(line['history0']-next(x['cost'] for x in scores if x['z']==line['z'] and x['type']==line['type'] and x['scenario']=='shock'))<1e-10
  assert line['history10']==ten_cost(line['z'],line['type'],'shock')
 for z,item in summary['overall'].items():
  for label in ('history0','history10'):assert abs(item[label]-statistics.mean(x[label] for x in summary['by_type'] if x['z']==int(z)))<1e-10
 assert count==10800 and len(scores)==18
 manifest=read(ROOT/'docs/artifacts/base_stock_zero_history_completed_v1/manifest.json')
 import hashlib
 for p,item in manifest['files'].items():assert hashlib.sha256(gzip.decompress((ROOT/p).read_bytes())).hexdigest()==item['source_sha256']
 result=dict(status='passed',episodes=18,rows=count,source_hashes=True,costs_and_tables_recomputed=True,archive_files=len(manifest['files']),numerical_boundaries=old.numerical.BOUNDARIES,api=0)
 with (OUT/'independent_audit.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2)
 print('ZERO_HISTORY_INDEPENDENT_AUDIT_PASSED',count,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run','verify','audit','check-publication'));a=p.parse_args()
 {'register':register,'run':run,'verify':verify,'audit':audit,'check-publication':lambda:old.check_publication(OUT/'completed_publication.json')}[a.action]()
