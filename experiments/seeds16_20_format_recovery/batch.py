"""Recovery with unchanged total budget, historical physical calls counted once."""
import argparse,csv,hashlib,importlib.util,inspect,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=ROOT/'results/seeds16_20_fixed_comparison/format_recovery_v1';OLD=ROOT/'results/seeds16_20_fixed_comparison/v2'
PLAN=ROOT/'docs/superpowers/plans/2026-10-16-seeds16-20-format-recovery.md'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
base=module('registered_extension_driver_v2',ROOT/'experiments/seeds16_20_fixed_comparison/batch.py');base.OUT=OUT;base.HERE=HERE
read,write,sha=base.read,base.write,base.sha
def source_files():
 r=module('recovery_registered_runner',HERE/'runner.py');r.setup('sundial',16)
 files={str(ROOT/p):h for p,h in r.core.source_hashes().items()};files[str(r.predictor.ADAPTER)]=sha(r.predictor.ADAPTER)
 for p in r.predictor.base.base.MODEL.rglob('*'):
  if p.is_file():files[str(p)]=sha(p)
 for p in OLD.rglob('*'):
  if p.is_file():files[str(p)]=sha(p)
 for p in [PLAN,*HERE.glob('*.py')]:files[str(p)]=sha(p)
 previous=read(OLD/'registration.json');files.update(previous['files'])
 return files
def verify():
 r=read(OUT/'registration.json')
 for p,h in r['files'].items():assert sha(Path(p))==h,p
 return r
base.verify=verify
def prepare():
 assert not OUT.exists();OUT.mkdir(parents=True);files=source_files();write(OUT/'input.json',read(OLD/'input.json'));files[str(OUT/'input.json')]=sha(OUT/'input.json');write(OUT/'preparation_freeze.json',dict(files=files,api=0))
 for mode in ('merton','sundial'):
  with (OUT/f'client_fixture_{mode}.log').open('x',encoding='utf-8') as log:p=subprocess.run([str(base.PYTHON),str(HERE/'fixture.py'),mode,str(OUT/'client_fixture'/mode)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
  assert p.returncode==0,mode
 path=OUT/'replay_fixture/seed16_merton'
 with (OUT/'replay_fixture.log').open('x',encoding='utf-8') as log:p=subprocess.run(base.command(16,'merton',path,True),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
 assert p.returncode==0,'Replay fixture failed; preserve output'
 def rows(path):
  with path.open(encoding='utf-8',newline='') as f:return {(x['group'],x['scenario'],x['trace'],x['period'],x['node']):x for x in csv.DictReader(f)}
 old=rows(OLD/'runs/seed16_merton/periods.csv');new=rows(path/'periods.csv');assert len(old)==6600 and all(new[k]==v for k,v in old.items())
 c=read(path/'calls.json');assert len(c)==18 and all(x.get('reused_from') for x in c)
 for p,h in files.items():assert sha(Path(p))==h,p
 write(OUT/'preflight.json',dict(status='passed',network_requests=0,client_modes=['merton','sundial'],replay_episodes=12,replay_rows=7200,old_completed_rows_exact=6600,reused_http_records=18,fake_missing_event_not_performance=True));print('FORMAT_RECOVERY_PREFLIGHT_PASSED',flush=True)
def register():
 assert not (OUT/'registration.json').exists();assert read(OUT/'preflight.json')['status']=='passed';prior=read(OLD/'registration.json');files=dict(read(OUT/'preparation_freeze.json')['files'])
 for p,h in files.items():assert sha(Path(p))==h,p
 for p in OUT.rglob('*'):
  if p.is_file():files[str(p)]=sha(p)
 write(OUT/'registration.json',dict(files=files,tasks=prior['tasks'],contracts=prior['contracts'],episodes=90,rows=54000,historical_http=20,historical_semantic=17,first_http_cap=480,first_semantic_cap=241,total_http_cap=960,total_semantic_cap=480,new_semantic_remaining_cap=463,first_no_quota_max_http=468,first_no_quota_max_semantic=241,successful_reuse_http=18,diagnostic_protocol_changed=True,all_failures_preserved=True,created=time.time()))
 paths=[p for p in OUT.rglob('*') if p.is_file()]+[p for p in OLD.rglob('*') if p.is_file()]+list(HERE.glob('*.py'))+[PLAN]
 public=base.ref.reuse.archive(ROOT/'docs/artifacts/seeds16_20_format_recovery_preregistration_v1',paths);write(OUT/'publication.json',dict(files=public));print('FORMAT_RECOVERY_REGISTERED',flush=True)
def physical_calls():
 history=[dict(source=str(OLD/'runs/seed16_merton/calls.json'),**x) for x in read(OLD/'runs/seed16_merton/calls.json')]
 new=[dict(source=str(p),**x) for p in (OUT/'runs').rglob('calls.json') for x in read(p) if not x.get('reused_from')] if (OUT/'runs').exists() else []
 return history+new
base.calls=physical_calls
def archive():
 paths=[p for p in OUT.rglob('*') if p.is_file() and p.name not in ('driver.log','error.log')]+list(HERE.glob('*.py'))+[PLAN]
 public=base.ref.reuse.archive(ROOT/'docs/artifacts/seeds16_20_format_recovery_completed_v1',paths);write(OUT/'completed_publication.json',dict(files=public,active_wrapper_logs_excluded=True))
base.archive=archive
run_source=inspect.getsource(base.run)
needle="sum(x['attempt']==1 for x in first)+24<=240";assert run_source.count(needle)==1;run_source=run_source.replace(needle,"sum(x['attempt']==1 for x in first)+24<=241")
needle="http=len(raw),semantic=sum(x['attempt']==1 for x in raw),fatal=fatal";assert run_source.count(needle)==1
run_source=run_source.replace(needle,"http=sum(not x.get('reused_from') for x in raw),semantic=sum(x['attempt']==1 and not x.get('reused_from') for x in raw),reused_http=sum(bool(x.get('reused_from')) for x in raw),logical_http=len(raw),fatal=fatal")
run_source=run_source.replace("print('SEEDS16_20_COMPARISON_COMPLETED'","print('SEEDS16_20_FORMAT_RECOVERY_COMPLETED'")
def run():
 ns=dict(base.__dict__);exec(compile(run_source,str(HERE/'batch.py'),'exec'),ns);ns['run']()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','register','verify','run'));a=p.parse_args();{'prepare':prepare,'register':register,'verify':verify,'run':run}[a.action]()
