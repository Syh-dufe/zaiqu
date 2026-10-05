"""Verify staged Git bytes, gzip reversibility, and credential absence before push."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
PUBLIC=ROOT/'docs/artifacts/joint_baseline_confirmation_v1_preregistration'


def sha(b):return hashlib.sha256(b).hexdigest()


def main():
    manifest=json.loads((PUBLIC/'export_manifest.json').read_text(encoding='utf-8'))
    for record in manifest['files']:
        stored=(PUBLIC/record['public_path']).read_bytes()
        assert sha(stored)==record['stored_sha256']
        raw=gzip.decompress(stored) if record['compression']=='gzip' else stored
        assert sha(raw)==record['raw_sha256']
    key=os.environ.get('DEEPSEEK_API_KEY','').encode();assert key
    paths=sorted(p for p in PUBLIC.rglob('*') if p.is_file())
    proc=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    try:
        for path in paths:
            proc.stdin.write((':'+path.relative_to(ROOT).as_posix()+'\n').encode('utf-8'));proc.stdin.flush()
            header=proc.stdout.readline().decode().split();assert len(header)==3 and header[1]=='blob',header
            stored=proc.stdout.read(int(header[2]));assert proc.stdout.read(1)==b'\n'
            assert stored==path.read_bytes(),str(path)
            assert key not in stored,str(path)
        proc.stdin.close();assert proc.wait()==0
    finally:
        if proc.poll() is None:proc.kill()
    for line in subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).split(b'\0'):
        if line:
            path=ROOT/line.decode('utf-8');assert key not in path.read_bytes(),str(path)
    print('GIT_EXACT_BYTES_PASSED',len(paths),'files; raw gzip and staged credential absence passed')


if __name__=='__main__':main()
