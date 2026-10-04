"""Verify and losslessly archive the completed neutral development pilot; no API."""
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import statistics

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'results/online_llm_neutral/development_v3'
EXPORT = ROOT / 'docs/artifacts/online_llm_neutral_development_v3'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not EXPORT.exists(), 'Archive already exists; refuse overwrite'
    spec = importlib.util.spec_from_file_location('neutral_archive_analyzer', ROOT / 'experiments/online_llm_neutral/analyze.py')
    analyzer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyzer)
    manifest = read(SOURCE / 'manifest.json')
    frozen = read(SOURCE / 'freeze.json')
    done = read(SOURCE / 'completed.json')
    summary = read(SOURCE / 'summary.json')
    assert digest(SOURCE / 'summary.json') == done['summary_sha256']
    assert digest(SOURCE / 'freeze.json') == manifest['freeze_sha256']
    assert digest(SOURCE / 'inputs.json') == manifest['input_sha256']
    for rel, expected in frozen['source_sha256'].items():
        assert digest(ROOT / rel) == digest(SOURCE / 'sources' / rel) == expected
    records, audits, calls = [], [], []
    for seed in (11, 12):
        folder = SOURCE / f'seed{seed}'
        contract = manifest['contracts'][str(seed)]
        for path, expected in contract['model_files'].items():
            assert digest(Path(path)) == expected
        training = analyzer.CORE.training(seed)
        for name, expected in contract['training_metadata'].items():
            assert digest(training / name) == expected
        audits.append(analyzer.audit_run(folder, read(SOURCE / 'inputs.json'), contract))
        with (folder / 'periods.csv').open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        for episode in read(folder / 'episodes.json'):
            local = [r for r in rows if r['group'] == episode['group'] and r['scenario'] == episode['scenario'] and int(r['trace']) == episode['trace']]
            assert len(local) == 600
            assert len({(int(r['period']), int(r['node'])) for r in local}) == 600
            assert all(float(r['cost']) == int(r['inventory']) + int(r['backlog']) for r in local)
            cost = statistics.mean(float(r['cost']) for r in local)
            backlog = statistics.mean(int(r['backlog']) for r in local if int(r['node']) == 0)
            assert math.isclose(cost, episode['cost'], abs_tol=1e-9)
            assert math.isclose(backlog, episode['downstream_backlog'], abs_tol=1e-9)
            records.append(dict(seed=seed, group=episode['group'], scenario=episode['scenario'], trace=episode['trace'], cost=cost, backlog=backlog))
        calls.extend(read(folder / 'calls.json'))
    assert len(records) == 64 and sum(a['node_periods'] for a in audits) == 38400
    for pair in summary['paired_deltas']:
        left, right = [next(r for r in records if r['seed'] == pair['seed'] and r['trace'] == pair['trace'] and r['scenario'] == 'shock' and r['group'] == method) for method in (pair['reference'], pair['method'])]
        assert math.isclose(right['cost'] - left['cost'], pair['cost_delta'], abs_tol=1e-9)
        assert math.isclose(right['backlog'] - left['backlog'], pair['backlog_delta'], abs_tol=1e-9)
    assert summary['all_unfavorable_pairs'] == [r for r in summary['paired_deltas'] if r['cost_delta'] > 0 or r['backlog_delta'] > 0]
    for comparison in summary['comparisons']:
        pairs = [r for r in summary['paired_deltas'] if r['reference'] == comparison['reference'] and r['method'] == comparison['method']]
        assert len(pairs) == comparison['pairs'] == 8
        for field in ('cost', 'backlog'):
            assert math.isclose(statistics.mean(r[f'{field}_delta'] for r in pairs), comparison[f'mean_{field}_delta'], abs_tol=1e-9)
    assert len(calls) == summary['api_requests'] == done['api_requests'] == 196
    assert analyzer.usage(calls) == summary['usage']
    paths = [p for p in SOURCE.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += [SOURCE.parent / f'development_v3_{suffix}.log' for suffix in ('driver', 'error')]
    secret = os.environ.get('DEEPSEEK_API_KEY')
    assert secret, 'Credential presence required for private absence audit'
    assert all(secret.encode() not in p.read_bytes() for p in paths), 'Credential detected; do not archive'
    EXPORT.mkdir(parents=True)
    originals, archives = {}, {}
    heavy = {'periods.csv', 'scores.json', 'information_audits.json', 'delivered_reports.json'}
    for path in paths:
        rel = path.relative_to(SOURCE) if path.is_relative_to(SOURCE) else Path('driver_logs') / path.name
        target = EXPORT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        originals[rel.as_posix()] = digest(path)
        if path.name in heavy:
            target = target.with_name(target.name + '.gz')
            with target.open('wb') as raw:
                with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as stream:
                    stream.write(path.read_bytes())
            assert hashlib.sha256(gzip.decompress(target.read_bytes())).hexdigest() == digest(path)
        else:
            shutil.copy2(path, target)
            assert digest(target) == digest(path)
        archives[target.relative_to(EXPORT).as_posix()] = digest(target)
    verification = dict(status='verified', episodes=64, node_periods=38400, api_requests=196,
        usage=summary['usage'], development_only=True, raw_metric_pair_recomputation='passed',
        causal_budget_execution_audits=audits, source_model_metadata_hashes='passed',
        configured_credential_absent=True, originals_preserved=True,
        outcome='No new variant qualified against original online feedback', currency_cost=None)
    (EXPORT / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding='utf-8')
    archives['verification.json'] = digest(EXPORT / 'verification.json')
    (EXPORT / 'export_hashes.json').write_text(json.dumps(dict(original_sha256=originals, archive_sha256=archives), indent=2), encoding='utf-8')
    print('NEUTRAL_ARCHIVE_VERIFIED', len(originals), 'files;64episodes38400rows196HTTP;noAPI', flush=True)


if __name__ == '__main__':
    main()
