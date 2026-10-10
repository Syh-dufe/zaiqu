"""Preserve crash evidence and check completed artifacts without APIs or replay."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'results/submission_required/v1'
OUTPUT=ROOT/'results/reboot_diagnosis/20261010_v1'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(blob):return hashlib.sha256(blob).hexdigest()

def main():
    if OUTPUT.exists():raise RuntimeError('Preserve prior diagnosis')
    OUTPUT.mkdir(parents=True)
    progress=read(OLD/'progress.json');mismatches=[];checked=0
    for task in progress['completed_tasks']:
        directory=OLD/'runs'/task['label']
        for name,key in [('completed.json','completed_sha256'),('audit.json','audit_sha256')]:
            if sha((directory/name).read_bytes())!=task[key]:mismatches.append(str(directory/name))
        for name,expected in read(directory/'audit.json')['raw_sha256'].items():
            checked+=1
            if sha((directory/name).read_bytes())!=expected:mismatches.append(str(directory/name))
    freeze=read(OLD/'freeze.json')
    for name,expected in freeze['source_sha256'].items():
        if sha((ROOT/name).read_bytes())!=expected:mismatches.append(name)
    paths=[OLD/'progress.json',OLD/'attempts.json']
    paths += [p for p in (OLD/'runs'/progress['current_task']).rglob('*') if p.is_file()]
    fixture=ROOT/'results/online_llm_guard_pool/offline_fixture_v1'
    paths += [p for p in fixture.rglob('*') if p.is_file()]
    entries=[]
    for path in paths:
        blob=path.read_bytes()
        target=OUTPUT/'preserved'/(str(path.relative_to(ROOT))+'.gz')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(gzip.compress(blob,mtime=0))
        assert gzip.decompress(target.read_bytes())==blob
        entries.append(dict(path=str(path.relative_to(ROOT)),bytes=len(blob),null_bytes=blob.count(bytes([0])),sha256=sha(blob),gzip_sha256=sha(target.read_bytes())))
    result=dict(status='diagnosed_not_restarted',completed_tasks=len(progress['completed_tasks']),completed_raw_files_checked=checked,
        completed_or_source_mismatches=mismatches,current_task=progress['current_task'],preserved=entries,
        api_calls=0,training_updates=0,crash_incomplete_outputs_excluded=True,
        interrupted_call_usage_unknown=True,no_claim_of_complete_http_or_token_records=True)
    (OUTPUT/'diagnosis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('REBOOT_EVIDENCE_PRESERVED',len(entries),'COMPLETED_RAW_CHECKED',checked,'MISMATCHES',len(mismatches))

if __name__=='__main__':main()
