"""Preserve the diagnosed failed driver and successful first task before continuation."""
import gzip
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REG=ROOT/'results/joint_baseline_confirmation/audit_import_recovery_v1'
OLD=ROOT/'results/joint_baseline_confirmation/confirmation_v1'
PUBLIC=ROOT/'docs/artifacts/joint_baseline_audit_import_recovery_v1'


def sha(b):return hashlib.sha256(b).hexdigest()


def main():
    assert not PUBLIC.exists(),'Refuse overwrite'
    record=json.loads((REG/'registration.json').read_text(encoding='utf-8'))
    assert record['status']=='passed_no_api_audit_recovery' and record['remaining_tasks']==49
    paths=set(Path(p) for p in record['hashes'])|set(Path(p) for p in record['completed_task_hashes'])
    paths.update(p for p in REG.rglob('*') if p.is_file())
    paths.update(OLD/name for name in ('failed.json','error.log','driver.log','launch.json','wrapper_launch.json','progress.json','seed11_batch01.log'))
    for p,expected in {**record['hashes'],**record['completed_task_hashes']}.items():assert sha(Path(p).read_bytes())==expected
    key=os.environ.get('DEEPSEEK_API_KEY','').encode();assert key
    PUBLIC.mkdir(parents=True);files=[]
    for path in sorted(paths):
        data=path.read_bytes();assert key not in data,str(path)
        relative=path.relative_to(ROOT);target=PUBLIC/relative
        compressed=len(data)>1000000 and path.suffix in ('.csv','.json','.log')
        if compressed:target=target.with_suffix(target.suffix+'.gz')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(gzip.compress(data,mtime=0) if compressed else data)
        stored=target.read_bytes();assert (gzip.decompress(stored) if compressed else stored)==data
        files.append(dict(source=str(path),public_path=target.relative_to(PUBLIC).as_posix(),raw_sha256=sha(data),
                          stored_sha256=sha(stored),compression='gzip' if compressed else 'none'))
    (PUBLIC/'export_manifest.json').write_text(json.dumps(dict(files=files,first_task_reused_without_rerun=True,
        first_task_episodes=24,first_task_rows=14400,first_task_http=34,recovery_registration_api_calls=0,
        remaining_tasks=49,original_failure_preserved=True),indent=2),encoding='utf-8')
    print('RECOVERY_ARCHIVED',len(files),'raw files, key absence and lossless bytes verified')


if __name__=='__main__':main()
