"""Preserves deployment and original failed fixture, uses explicit typed auditor."""
import argparse,hashlib,inspect,os,sys,gzip,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT/'experiments/sundial_closed_loop_development'))
import batch as old
runner=old.runner;core=runner.core
new_audit=runner.module('sundial_registered_float_audit',HERE/'audit.py')
RECOVERY=ROOT/'results/sundial_closed_loop_development/audit_recovery_v1'
FIXTURE=ROOT/'results/sundial_closed_loop_development/no_api_fixture_v1'
PROTOCOL=ROOT/'docs/superpowers/plans/2026-10-14-sundial-closed-loop-float-audit-recovery.md'
old_verify=old.verify

def hashes():return {str(p):old.digest(p) for p in list(HERE.glob('*.py'))+[PROTOCOL]}
def verify():
 result=old_verify()
 if (RECOVERY/'registration.json').exists():
  registration=old.read(RECOVERY/'registration.json')
  for p,sha in registration['recovery_sha256'].items():assert old.digest(p)==sha,p
  for p,sha in registration['original_fixture_sha256'].items():assert old.digest(p)==sha,p
 return result
old.verify=verify;old.auditor=new_audit

def fixture():
 verify();assert not RECOVERY.exists();assert (FIXTURE/'completed.json').exists() and (FIXTURE/'preflight_failed.json').exists()
 done=old.read(FIXTURE/'completed.json');assert done['episodes']==32 and done['calls']<=128
 RECOVERY.mkdir(parents=True);copy=RECOVERY/'fixture_copy';copy.mkdir();bound={}
 for p in FIXTURE.rglob('*'):
  if not p.is_file():continue
  dest=copy/p.relative_to(FIXTURE);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);assert old.digest(p)==old.digest(dest);bound[str(p)]=old.digest(p)
 if (copy/'audit.json').exists():(copy/'audit.json').rename(copy/'original_partial_audit.json')
 data=old.read(copy/'demands.json');contract=old.read(copy/'protocol.json')
 result=new_audit.audit(runner,copy,data,contract['expected_parameter_sha256'],True)
 score=next(r for r in old.read(copy/'scores.json') if r['group']=='native_sundial' and 'forecast_audit' in r);a=score['forecast_audit'];v=a['prediction']
 raw,seeds=runner.predictor.sample_blocks(v['block_history'],len(v['raw_blocks'][0]),a['stream_identity'])
 import numpy as np
 assert np.array_equal(raw,np.asarray(v['raw_blocks'],dtype=np.float32)) and seeds==v['sampling_seeds']
 old.write(RECOVERY/'preflight_recovery_passed.json',dict(**result,network_requests=0,recorded_sundial_inference_reproduced=True,not_performance_evidence=True,original_simulation_reused=True))
 old.write(RECOVERY/'registration.json',dict(recovery_sha256=hashes(),original_fixture_sha256=bound,api=0,simulation_reruns=0))
 print('SUNDIAL_FLOAT_AUDIT_RECOVERY_FIXTURE_PASSED',flush=True)

def register():
 verify();source=inspect.getsource(old.register)
 needle="fixture=ROOT/'results/sundial_closed_loop_development/no_api_fixture_v1/preflight_passed.json'"
 assert source.count(needle)==1
 source=source.replace(needle,"fixture=ROOT/'results/sundial_closed_loop_development/audit_recovery_v1/preflight_recovery_passed.json'")
 ns=dict(old.__dict__);exec(compile(source,str(Path(__file__)),'exec'),ns);ns['register']()
 registration=old.read(old.OUT/'registration.json');registration['float_audit_recovery_sha256']=old.digest(RECOVERY/'registration.json');old.write(old.OUT/'registration.json',registration)

def publish():
 verify();old.publish();package=old.PACKAGE;manifest=old.read(package/'manifest.json');publication=old.read(old.OUT/'publication.json');key=os.environ['DEEPSEEK_API_KEY'].encode()
 files=list(HERE.glob('*.py'))+[PROTOCOL]+[p for p in RECOVERY.rglob('*') if p.is_file()]+[p for p in (ROOT/'results/sundial_closed_loop_development/development_v1').glob('*') if p.is_file()]
 for index,p in enumerate(files):
  blob=p.read_bytes();assert key not in blob;dest=package/'recovery'/f'{index:04d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(blob,mtime=0));assert gzip.decompress(dest.read_bytes())==blob
  rel=dest.relative_to(ROOT).as_posix();manifest['files'][rel]=old.digest(dest);manifest['origins'][rel]=dict(source=str(p),sha256=old.digest(p));publication['git_files'][rel]=old.digest(dest)
 old.write(package/'manifest.json',manifest);publication['git_files'][(package/'manifest.json').relative_to(ROOT).as_posix()]=old.digest(package/'manifest.json');old.write(old.OUT/'publication.json',publication)
 print('SUNDIAL_FULL_FAILURE_RECOVERY_REGISTRATION_EXPORTED',len(publication['git_files']),flush=True)

def run():
 verify();assert old.read(old.OUT/'registration.json')['float_audit_recovery_sha256']==old.digest(RECOVERY/'registration.json')
 old.run()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=('fixture','register','publish','verify','run'));a=parser.parse_args()
 if a.action in ('register','publish','run'):old.common.key_from_user()
 {'fixture':fixture,'register':register,'publish':publish,'verify':verify,'run':run}[a.action]()
