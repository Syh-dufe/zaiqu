"""Lossless posthoc Base-stock appendix export; no rollout, API or Git mutation.

Run only after results/base_stock_appendix/posthoc_v1/completed.json exists.
The export destination is exclusive: an existing archive is never overwritten.
"""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'results/base_stock_appendix/posthoc_v1'
PUBLIC = ROOT / 'docs/artifacts/base_stock_appendix_posthoc_v1'
PHASE = 'posthoc_additional_baseline_comparison'
COMPRESSIBLE = {'.json', '.csv', '.log', '.txt', '.jsonl'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def user_key():
    """Windows User environment only. The value is never printed or persisted."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as environment:
        value, kind = winreg.QueryValueEx(environment, 'DEEPSEEK_API_KEY')
    require(kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and isinstance(value, str) and bool(value.strip()),
            'Windows User key is required solely for archive absence verification')
    return value.strip()


def sensitive_absent(data, key):
    variants = [key.encode('utf-8'), key.encode('utf-16-le'), key.encode('utf-16-be'),
                json.dumps(key)[1:-1].encode('utf-8'), base64.b64encode(key.encode('utf-8'))]
    require(not any(value in data for value in variants), 'Sensitive credential detected; archive stopped')
    require(re.search(rb'sk-[A-Za-z0-9_-]{20,}', data) is None, 'Credential-shaped material detected; archive stopped')


def resolved(name):
    path = Path(name)
    return path if path.is_absolute() else ROOT / path


def add_file(paths, source, expected=None):
    source = Path(source).resolve()
    require(source.is_file() and not source.is_symlink(), 'Missing or unsupported archive source')
    if expected is not None:
        require(sha(source.read_bytes()) == expected, 'Frozen archive source hash changed')
    paths.add(source)


def add_tree(paths, root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), 'Missing or unsupported archive source directory')
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'Symlink source refused for complete archive')
        if path.is_file():
            add_file(paths, path)


def collect_sources(freeze, manifest):
    paths = set()
    add_tree(paths, SOURCE)
    original = Path(freeze['original_root'])
    require(original == Path(manifest['original_root']), 'Original source identity mismatch')
    # Entire old parent includes root logs, both recovery trees and offline proof
    # provenance, in addition to every completed and failed child task.
    add_tree(paths, original.parent)
    for dirname in ('audit_import_recovery_v1', 'recharge_recovery_v1'):
        require((original.parent / dirname).is_dir(), 'Historical recovery provenance missing')
    for archive in sorted((ROOT / 'docs/artifacts').glob('joint_baseline_*')):
        if archive.is_dir():
            add_tree(paths, archive)
    for field in ('source_sha256', 'original_files_sha256'):
        require(isinstance(freeze.get(field), dict) and bool(freeze[field]), 'Frozen source inventory missing')
        for name, expected in freeze[field].items():
            add_file(paths, resolved(name), expected)
    require(set(freeze['training_contracts']) == {str(s) for s in (11, 12, 13, 14, 15)}, 'Five training contracts required')
    for contract in freeze['training_contracts'].values():
        metadata_candidates = []
        for algorithm in ('happo', 'ippo'):
            inventory = contract[algorithm + '_contract']['hashes']
            require(bool(inventory), 'Frozen model/metadata inventory missing')
            for name, expected in inventory.items():
                source = resolved(name)
                add_file(paths, source, expected)
                metadata_candidates.append((source, expected))
        for name, expected in contract.get('model_files', {}).items():
            add_file(paths, resolved(name), expected)
        for name, expected in contract.get('source_sha256', {}).items():
            add_file(paths, resolved(name), expected)
        for name, expected in contract.get('training_metadata', {}).items():
            path = Path(name)
            matches = [source for source, value in metadata_candidates if source.name == path.name and value == expected]
            if path.is_absolute():
                matches = [path]
            require(bool(matches), 'Frozen training metadata cannot be resolved')
            for source in matches:
                add_file(paths, source, expected)
    for entry in manifest['input_batches']:
        add_file(paths, resolved(entry['path']), entry['sha256'])
    library = ROOT / 'docs/artifacts/operator_discovery_v1/repaired_library.json'
    add_file(paths, library, freeze['library_sha256'])
    add_file(paths, Path(__file__))
    return sorted(paths)


def relative_destination(source):
    source = Path(source).resolve()
    if source.is_relative_to(ROOT.resolve()):
        relative = source.relative_to(ROOT.resolve())
    else:
        relative = Path('external_absolute') / sha(str(source.parent).encode('utf-8'))[:24] / source.name
    # Historical nested snapshots can exceed Windows MAX_PATH after export.
    # The manifest preserves the complete source identity; short destination
    # names retain exact contents without depending on long-path OS settings.
    if len(str(PUBLIC / relative)) > 230:
        relative = Path('long_paths') / (sha(str(source).encode('utf-8')) + source.suffix)
    return relative


def export_file(source, target_root, key, threshold=1000000):
    data = Path(source).read_bytes()
    sensitive_absent(data, key)
    sensitive_absent(str(source).encode('utf-8'), key)
    expanded = gzip.decompress(data) if data[:2] == b'\x1f\x8b' else None
    if expanded is not None:
        sensitive_absent(expanded, key)
    relative = relative_destination(source)
    compressed = expanded is None and len(data) > threshold and Path(source).suffix.lower() in COMPRESSIBLE
    if compressed:
        relative = relative.with_suffix(relative.suffix + '.gz')
    destination = Path(target_root) / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    stored = gzip.compress(data, mtime=0) if compressed else data
    with destination.open('xb') as stream:
        stream.write(stored)
    actual = destination.read_bytes()
    require(actual == stored, 'Stored archive bytes differ')
    require((gzip.decompress(actual) if compressed else actual) == data, 'Lossless archive round-trip failed')
    sensitive_absent(actual, key)
    if actual[:2] == b'\x1f\x8b':
        sensitive_absent(gzip.decompress(actual), key)
    record = dict(source=str(source), public_path=relative.as_posix(), raw_sha256=sha(data),
                  stored_sha256=sha(actual), raw_bytes=len(data), stored_bytes=len(actual),
                  compression='gzip' if compressed else 'source_gzip' if expanded is not None else 'none')
    if expanded is not None:
        record.update(source_gzip_decompressed_sha256=sha(expanded), source_gzip_decompressed_bytes=len(expanded))
    return record


def verify_archive(public, key, check_sources=True, check_git=False):
    public = Path(public)
    manifest = read(public / 'export_manifest.json')
    require(manifest['phase'] == PHASE and manifest['new_api_requests'] == 0, 'Archive phase/API identity mismatch')
    records = manifest['files']
    require(len(records) == manifest['files_count'] and len({r['public_path'] for r in records}) == len(records),
            'Archive file inventory mismatch')
    for record in records:
        path = public / record['public_path']
        require(path.resolve().is_relative_to(public.resolve()), 'Archive inventory escapes export directory')
        data = path.read_bytes()
        require(sha(data) == record['stored_sha256'] and len(data) == record['stored_bytes'], 'Archive stored hash/size mismatch')
        sensitive_absent(data, key)
        raw = gzip.decompress(data) if record['compression'] == 'gzip' else data
        require(sha(raw) == record['raw_sha256'] and len(raw) == record['raw_bytes'], 'Archive raw hash/size mismatch')
        sensitive_absent(raw, key)
        if data[:2] == b'\x1f\x8b':
            expanded = gzip.decompress(data)
            sensitive_absent(expanded, key)
            if 'source_gzip_decompressed_sha256' in record:
                require(sha(expanded) == record['source_gzip_decompressed_sha256'], 'Existing gzip expanded hash mismatch')
        if check_sources:
            require(sha(Path(record['source']).read_bytes()) == record['raw_sha256'], 'Original source changed after export')
        if check_git:
            relative = path.relative_to(ROOT).as_posix()
            result = subprocess.run(['git', 'show', f'HEAD:{relative}'], cwd=ROOT, capture_output=True)
            require(result.returncode == 0 and result.stdout == data, 'Git committed archive bytes differ or are absent')
    for path in public.rglob('*'):
        if path.is_file():
            data = path.read_bytes()
            sensitive_absent(data, key)
            if data[:2] == b'\x1f\x8b':
                sensitive_absent(gzip.decompress(data), key)
    return dict(files=len(records), raw_bytes=sum(r['raw_bytes'] for r in records),
                stored_bytes=sum(r['stored_bytes'] for r in records), exact_bytes_verified=True,
                existing_gzip_streams=sum('source_gzip_decompressed_sha256' in r for r in records),
                sensitive_absence_verified=True, git_bytes_verified=check_git)


def export():
    require(not PUBLIC.exists(), 'Existing archive must be preserved; export destination is exclusive')
    done, summary = read(SOURCE / 'completed.json'), read(SOURCE / 'summary.json')
    freeze, manifest = read(SOURCE / 'freeze.json'), read(SOURCE / 'manifest.json')
    require(done['status'] == 'completed' and done['phase'] == PHASE and done['posthoc'] is True
            and done['prospective_independent_confirmation'] is False, 'Completed posthoc appendix required')
    require(done['episodes'] == 1360 and done['node_periods'] == 816000 and done['new_episodes'] == 160
            and done['new_node_periods'] == 96000 and done['new_api_requests'] == done['api_requests'] == 0,
            'Registered appendix counts/API identity mismatch')
    require(sha((SOURCE / 'summary.json').read_bytes()) == done['summary_sha256'], 'Completed summary hash mismatch')
    require(sha((SOURCE / 'independent_audit.json').read_bytes()) == done['audit_sha256'], 'Independent audit hash mismatch')
    require(sha((SOURCE / 'freeze.json').read_bytes()) == manifest['freeze_sha256'], 'Freeze hash mismatch')
    require(summary['posthoc'] is True and summary['new_api_requests'] == 0
            and summary['prospective_independent_confirmation'] is False, 'Summary posthoc disclosure missing')
    paths = collect_sources(freeze, manifest)
    key = user_key()
    # Validate every source before creating the exclusive destination, leaving
    # no secret-bearing partial output if source validation fails.
    for path in paths:
        data = path.read_bytes()
        sensitive_absent(data, key)
        sensitive_absent(str(path).encode('utf-8'), key)
        if data[:2] == b'\x1f\x8b':
            sensitive_absent(gzip.decompress(data), key)
    PUBLIC.mkdir(parents=True, exist_ok=False)
    records = [export_file(path, PUBLIC, key) for path in paths]
    (PUBLIC / '.gitattributes').write_bytes(b'** -text\n')
    export_manifest = dict(phase=PHASE, posthoc=True, prospective_independent_confirmation=False,
        new_api_requests=0, historical_api_requests=summary['historical_api_requests'],
        historical_semantic_requests=summary.get('historical_semantic_requests'),
        historical_token_usage=summary.get('historical_token_usage', {}),
        historical_rl_episodes=1200, new_base_stock_episodes=160, total_episodes=1360,
        historical_node_periods=720000, new_node_periods=96000, total_node_periods=816000,
        historical_failures_and_recovery_roots_included=True, all_original_metrics_preserved=True,
        source_root=str(SOURCE), files_count=len(records), files=records,
        exported_after_completion=True, windows_user_key_used_only_for_absence_check=True)
    (PUBLIC / 'export_manifest.json').write_text(json.dumps(export_manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    report = verify_archive(PUBLIC, key)
    (PUBLIC / 'export_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    sensitive_absent((PUBLIC / 'export_verification.json').read_bytes(), key)
    print('POSTHOC_APPENDIX_ARCHIVED', report['files'], 'files; exact source/store bytes and sensitive absence verified')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--export', action='store_true')
    mode.add_argument('--verify', action='store_true')
    mode.add_argument('--verify-git', action='store_true', help='Read-only committed Git byte comparison after commit')
    args = parser.parse_args()
    if args.export:
        export()
    else:
        report = verify_archive(PUBLIC, user_key(), check_git=args.verify_git)
        print('POSTHOC_APPENDIX_ARCHIVE_VERIFIED', report['files'], 'files; git_bytes_verified=', report['git_bytes_verified'])


if __name__ == '__main__':
    main()
