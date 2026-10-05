"""Publish preregistration and offline fixtures with lossless byte verification."""
import gzip
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REG=ROOT/'results/joint_baseline_confirmation/confirmation_v1'
FIXTURE=ROOT/'results/joint_baseline_confirmation/no_api_interface_v2'
PUBLIC=ROOT/'docs/artifacts/joint_baseline_confirmation_v1_preregistration'


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    assert not PUBLIC.exists(),'Preserve existing archive'
    assert read(REG/'preflight.json')['status']=='passed_no_api_or_rollout'
    assert read(FIXTURE/'completed.json')['status']=='passed'
    freeze=read(REG/'freeze.json');manifest=read(REG/'manifest.json')
    paths=set(p for parent in (REG,FIXTURE) for p in parent.rglob('*') if p.is_file())
    paths.update(ROOT/'results/joint_baseline_confirmation'/name for name in ('no_api_interface_v1.log','no_api_interface_v2.log'))
    paths.update(ROOT/p for p in freeze['source_sha256'])
    paths.update((ROOT/'docs/artifacts/online_llm_development_v1/inputs.json',ROOT/'docs/artifacts/operator_discovery_v1/repaired_library.json'))
    paths.update((ROOT/'results/joint_baseline_confirmation/offline_fixture_review.json',ROOT/'docs/2026-10-05-joint-baseline-code-review.md'))
    paths.add(ROOT/'docs/2026-10-05-joint-baseline-confirmation-registration.md')
    paths.update((ROOT/'external/liu-inventory/test_data/test_demand_merton').glob('*.txt'))
    for contract in freeze['training_contracts'].values():
        for algorithm in ('happo','ippo'):
            paths.update(Path(p) for p in contract[algorithm+'_contract']['hashes'])
    key=os.environ.get('DEEPSEEK_API_KEY','').encode();assert key,'User key needed only for absence check'
    PUBLIC.mkdir(parents=True);records=[]
    for source in sorted(paths):
        if '__pycache__' in source.parts:continue
        data=source.read_bytes();assert key not in data,str(source)
        if source.is_relative_to(ROOT):relative=source.relative_to(ROOT)
        else:relative=Path('external_absolute')/sha(str(source.parent).encode())[:12]/source.name
        compressed=len(data)>1000000 and source.suffix in ('.csv','.json','.log')
        destination=PUBLIC/relative
        if compressed:destination=destination.with_suffix(destination.suffix+'.gz')
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(gzip.compress(data,mtime=0) if compressed else data)
        stored=destination.read_bytes()
        assert (gzip.decompress(stored) if compressed else stored)==data
        records.append(dict(source=str(source),public_path=destination.relative_to(PUBLIC).as_posix(),
                            raw_sha256=sha(data),stored_sha256=sha(stored),compression='gzip' if compressed else 'none',bytes=len(data)))
    (PUBLIC/'export_manifest.json').write_text(json.dumps(dict(files=records,files_count=len(records),
        offline_fixture_only=True,formal_inputs_generated_after_method_freeze=True,
        api_calls_before_paid_launch=0,all_registered_cases_retained=True),indent=2),encoding='utf-8')
    print('ARCHIVED',len(records),'files; all raw/stored hashes and key absence verified')


if __name__=='__main__':main()
