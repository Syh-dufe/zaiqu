"""Lossless publication of no-API readiness and reboot recovery registration."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/submission_required'))
from common import key_from_user

def main():
    key_from_user();key=os.environ['DEEPSEEK_API_KEY'].encode()
    target=ROOT/'docs/artifacts/online_llm_guard_pool_readiness_v1'
    checkpoint=ROOT/'docs/artifacts/required_reboot_recovery_v1'
    # Idempotent continuation verifies existing bytes; never replaces differing files.
    target.mkdir(parents=True,exist_ok=True);checkpoint.mkdir(parents=True,exist_ok=True)
    files=list((ROOT/'experiments/online_llm_guard_pool').glob('*.py'))
    files+=list((ROOT/'experiments/online_llm_guard_pool_driver').glob('*.py'))
    files+=[ROOT/'docs/2026-10-10-online-guard-pool-readiness.md',
        ROOT/'docs/superpowers/specs/2026-10-10-online-guard-pool-design.md',ROOT/'docs/superpowers/plans/2026-10-10-online-guard-pool.md']
    fixture=ROOT/'results/online_llm_guard_pool/offline_fixture_v2'
    files+=[p for p in fixture.rglob('*') if p.is_file()]
    files += [ROOT/'results/online_llm_guard_pool'/name for name in ('offline_fixture_v2.log','offline_fixture_v2_error.log','offline_fixture_v2_launch.json')]
    manifest={}
    for path in files:
        blob=path.read_bytes();assert key not in blob
        dest=target/(str(path.relative_to(ROOT))+'.gz');dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert gzip.decompress(dest.read_bytes())==blob
        else:dest.write_bytes(gzip.compress(blob,mtime=0))
        assert gzip.decompress(dest.read_bytes())==blob
        manifest[str(dest.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(dest.read_bytes()).hexdigest()
    (target/'manifest.json').write_text(json.dumps(dict(files=manifest,lossless=True,credential_absent=True,api_requests=0),indent=2),encoding='utf-8')
    registration=ROOT/'results/submission_required/v1/reboot_resume_v1/registration.json'
    blob=registration.read_bytes();assert key not in blob
    if (checkpoint/'registration.json').exists():assert (checkpoint/'registration.json').read_bytes()==blob
    else:(checkpoint/'registration.json').write_bytes(blob)
    extra=[ROOT/'experiments/submission_required_reboot_recovery/resume.py',ROOT/'docs/superpowers/plans/2026-10-10-required-reboot-recovery.md',
        ROOT/'experiments/online_llm_artifacts/diagnose_reboot_20261010.py']
    extra += [p for p in (ROOT/'results/reboot_diagnosis/20261010_v1').rglob('*') if p.is_file()]
    recovery_manifest={}
    for index,path in enumerate(extra):
        blob=path.read_bytes();assert key not in blob
        # Short numbered archive names avoid Windows path length limits; retain full origin.
        dest=checkpoint/'files'/f'{index:04d}.gz';dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert gzip.decompress(dest.read_bytes())==blob
        else:dest.write_bytes(gzip.compress(blob,mtime=0))
        assert gzip.decompress(dest.read_bytes())==blob
        recovery_manifest[str(dest.relative_to(ROOT)).replace('\\','/')]=dict(source=str(path.relative_to(ROOT)),sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
    (checkpoint/'manifest.json').write_text(json.dumps(dict(files=recovery_manifest,lossless=True,credential_absent=True,
        unknown_interrupted_api_usage=True,conservative_reserved_http=176,conservative_reserved_semantic=88),indent=2),encoding='utf-8')
    print('READINESS_AND_RECOVERY_ARCHIVED',len(manifest),len(recovery_manifest))

if __name__=='__main__':main()
