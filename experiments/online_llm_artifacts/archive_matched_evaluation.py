"""Lossless evidence export after the fixed matched-shock supplementary evaluation."""
import gzip
import hashlib
import json
from pathlib import Path
import winreg

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'results/happo_matched_evaluation/appendix_v1'
DEST=ROOT/'docs/artifacts/happo_matched_evaluation_completed_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(b):return hashlib.sha256(b).hexdigest()
def main():
    assert read(SOURCE/'completed.json')['passed'] and not (SOURCE/'failed.json').exists()
    assert not DEST.exists();manifest=read(SOURCE/'manifest.json')
    files={ROOT/p for p in manifest['hashes']}
    files.update(p for p in SOURCE.rglob('*') if p.is_file())
    for seed in range(11,16):
        directory=ROOT/f'results/learning_curve/matched_shock_seed{seed}_v2'
        files.update(directory/n for n in ('config.json','completed.json','completion_audit.json','curve.csv','stability.json','mixed_demand_override.json'))
    files.update([Path(__file__),ROOT/'results/happo_matched_shock/formal_v2/completed.json'])
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as key:secret=winreg.QueryValueEx(key,'DEEPSEEK_API_KEY')[0].encode()
    except FileNotFoundError:secret=b''
    records=[];DEST.mkdir(parents=True)
    for src in sorted(files):
        payload=src.read_bytes();assert not secret or secret not in payload
        rel=src.relative_to(ROOT);target=DEST/'snapshot'/rel
        if src.suffix!='.pt':target=Path(str(target)+'.gz');stored=gzip.compress(payload,mtime=0)
        else:stored=payload
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(stored)
        decoded=gzip.decompress(target.read_bytes()) if target.suffix=='.gz' else target.read_bytes()
        assert decoded==payload
        records.append(dict(source=str(rel).replace('\\','/'),archive=str(target.relative_to(ROOT)).replace('\\','/'),original_sha256=digest(payload),stored_sha256=digest(stored),original_bytes=len(payload)))
    (DEST/'archive_manifest.json').write_text(json.dumps(dict(files=records,source_files=len(records),secrets_absent=True,gzip_roundtrip=True,scope='All evaluation outputs and frozen comparison dependencies; training intermediate checkpoints remain local'),indent=2),encoding='utf-8')
    print('ARCHIVED',len(records),sum(r['original_bytes'] for r in records))
if __name__=='__main__':main()
