"""Independently audit and losslessly archive shock-types v4 and its failed v3 attempt; no API."""
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'results/online_llm_shock_types/development_v4'
FAILED = ROOT / 'results/online_llm_shock_types/development_v3'
EXPORT = ROOT / 'docs/artifacts/online_llm_shock_types_development_v4'
HEAVY = {'periods.csv', 'scores.json', 'information_audits.json', 'delivered_reports.json'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_files(freeze):
    return {Path(relative): expected for relative, expected in freeze['source_sha256'].items()}


def collect_run_records(root, manifest):
    episodes_by_key = {}
    paired = []
    total_rows = total_episodes = 0
    notices_checked = 0
    runtime_failures = []
    observed_calls = []
    per_episode_recomputed = []
    for seed in (11, 12, 13, 14, 15):
        for batch in (1, 2):
            label = f'seed{seed}_batch{batch}'
            folder = root / 'runs' / label
            completed = read(folder / 'completed.json')
            episodes = read(folder / 'episodes.json')
            calls = read(folder / 'calls.json')
            with (folder / 'periods.csv').open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.DictReader(stream))
            assert completed['episodes'] == len(episodes) == 16
            assert completed['rows'] == len(rows) == 9600
            assert completed['training_updates'] == 0
            assert set(completed['parameter_checks']) == {'happo', 'online_feedback'}
            assert all(x['unchanged'] and x['before'] == x['after'] for x in completed['parameter_checks'].values())
            assert len({(int(r['period']), int(r['node']), r['group'], r['scenario'], int(r['trace'])) for r in rows}) == 9600
            for row in rows:
                assert math.isclose(float(row['cost']), int(row['inventory']) + int(row['backlog']), abs_tol=1e-9)
                assert 0 <= int(row['actual_order']) <= 20
            for episode in episodes:
                local = [r for r in rows if r['group'] == episode['group'] and r['scenario'] == episode['scenario']
                         and int(r['trace']) == episode['trace']]
                assert len(local) == 600
                cost = statistics.mean(float(r['cost']) for r in local)
                backlog = statistics.mean(int(r['backlog']) for r in local if int(r['node']) == 0)
                assert math.isclose(cost, episode['cost'], abs_tol=1e-9)
                assert math.isclose(backlog, episode['downstream_backlog'], abs_tol=1e-9)
                episodes_by_key[seed, batch, episode['group'], episode['scenario'], episode['trace']] = episode
                per_episode_recomputed.append(dict(seed=seed, batch=batch, group=episode['group'],
                    scenario=episode['scenario'], trace=episode['trace'], cost=cost, downstream_backlog=backlog))
                if episode['scenario'] == 'base':
                    assert episode['notification_period'] is None
                else:
                    event = read(Path(manifest['input_batches'][batch - 1]['path']))['events'][episode['trace']]
                    assert episode['notification_period'] == event['start_index'] + 3
            for call in calls:
                assert call['group'] == 'online_feedback' and call['scenario'] == 'shock'
            assert all(e['episode_http'] == 0 for e in episodes if e['group'] == 'happo' or e['scenario'] == 'base')
            assert all(e['episode_http'] <= 16 for e in episodes if e['scenario'] == 'shock')
            total_rows += len(rows)
            total_episodes += len(episodes)
            observed_calls.extend(calls)
            runtime_failures.extend(completed.get('runtime_failures', []))
            for trace, event in enumerate(read(Path(manifest['input_batches'][batch - 1]['path']))['events']):
                stop = event['start_index'] + 3
                for scenario in ('base', 'shock'):
                    limit = 201 if scenario == 'base' else stop
                    key = ('period', 'node', 'cost', 'inventory', 'backlog', 'actual_order')
                    select = lambda group: [tuple(row[k] for k in key) for row in rows
                        if row['group'] == group and row['scenario'] == scenario
                        and int(row['trace']) == trace and int(row['period']) < limit]
                    assert select('happo') == select('online_feedback')
                    notices_checked += 1
    assert total_episodes == 160 and total_rows == 96000
    for pair in read(root / 'summary.json')['paired_results']:
        seed, batch, trace = pair['seed'], pair['batch'], pair['trace']
        h = episodes_by_key[seed, batch, 'happo', 'shock', trace]
        l = episodes_by_key[seed, batch, 'online_feedback', 'shock', trace]
        assert math.isclose(l['cost'] - h['cost'], pair['shock_cost_delta'], abs_tol=1e-9)
        assert math.isclose(l['downstream_backlog'] - h['downstream_backlog'], pair['shock_backlog_delta'], abs_tol=1e-9)
        paired.append(pair)
    return dict(episodes=total_episodes, node_periods=total_rows, paired_results=paired,
        recomputed_episodes=per_episode_recomputed, normal_and_pre_notice_checks=notices_checked,
        runtime_failures=runtime_failures, calls=observed_calls)


def verify_inputs_and_models(manifest, freeze):
    unique_by_type = {}
    transforms = 0
    for entry in manifest['input_batches']:
        path = Path(entry['path'])
        assert digest(path) == entry['sha256']
        data = read(path)
        assert len(data['base']) == len(data['shock']) == len(data['events']) == 4
        for index, event in enumerate(data['events']):
            typ = event['type']
            unique_by_type.setdefault(typ, set()).add(tuple(data['base'][index][:200]))
            expected = list(data['base'][index])
            for part in event['intervals']:
                for t in range(part['start'], part['end']):
                    value = part['factor'] * data['base'][index][t]
                    expected[t] = min(20, math.ceil(value)) if part['factor'] > 1 else math.floor(value)
            assert expected == data['shock'][index]
            transforms += 1
    assert all(len(paths) == 2 for paths in unique_by_type.values()) and len(unique_by_type) == 4
    prior_manifest = read(FAILED / 'manifest.json')
    assert [x['sha256'] for x in manifest['input_batches']] == [x['sha256'] for x in prior_manifest['input_batches']]
    assert read(SOURCE / 'collision_diagnosis.json')['inputs_are_unseen'] is False
    for seed, model_contract in freeze['model_contracts'].items():
        for raw, expected in model_contract['model_files'].items():
            assert digest(Path(raw)) == expected
        audit = read(Path(model_contract['training_metadata_path']) if 'training_metadata_path' in model_contract else
                     Path('results/learning_curve') / ('curve_seed11_until_stable_v1' if seed == '11' else f'curve_seed{seed}_formal_v1') / 'completion_audit.json')
        assert audit['model_matches']['official_best']['sha256'] == model_contract['expected_parameter_sha256']
    return dict(unique_demand_paths_per_type={k: len(v) for k, v in unique_by_type.items()},
        shock_transform_checks=transforms, inputs_match_v3=True, model_files_and_best_parameter_hashes='verified')


def copy_and_hash(source, export, prefix, originals, archives):
    for path in sorted(p for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts):
        rel = Path(prefix) / path.relative_to(source)
        originals[rel.as_posix()] = digest(path)
        target = export / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.name in HEAVY:
            target = target.with_name(target.name + '.gz')
            with target.open('wb') as raw:
                with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as stream:
                    stream.write(path.read_bytes())
            assert hashlib.sha256(gzip.decompress(target.read_bytes())).hexdigest() == digest(path)
        else:
            shutil.copy2(path, target)
            assert digest(target) == digest(path)
        archives[target.relative_to(export).as_posix()] = digest(target)


def main():
    assert not EXPORT.exists(), 'Archive already exists; refuse overwrite'
    manifest = read(SOURCE / 'manifest.json')
    freeze = read(SOURCE / 'freeze.json')
    completed = read(SOURCE / 'completed.json')
    summary = read(SOURCE / 'summary.json')
    progress = read(SOURCE / 'progress.json')
    assert completed['status'] == 'completed' and completed['episodes'] == 160 and completed['node_periods'] == 96000
    assert summary['episodes'] == 160 and summary['node_periods'] == 96000 and len(summary['paired_results']) == 40
    assert digest(SOURCE / 'summary.json') == completed['summary_sha256']
    assert digest(SOURCE / 'freeze.json') == manifest['freeze_sha256']
    assert digest(ROOT / 'docs/superpowers/plans/2026-10-05-unseen-shock-types-repair-v4.md') == freeze['protocol_sha256']
    assert progress['status'] == 'completed' and progress['completed_runs'] == 10
    for rel, expected in source_files(freeze).items():
        assert digest(ROOT / rel) == expected
    for rel, expected in source_files(read(FAILED / 'freeze.json')).items():
        assert digest(ROOT / rel) == expected
    computed = collect_run_records(SOURCE, manifest)
    integrity = verify_inputs_and_models(manifest, freeze)
    prior_calls = read(FAILED / 'runs/seed11_batch1/calls.json')
    all_calls = computed['calls'] + prior_calls
    assert len(computed['calls']) == 337 and len(prior_calls) == 37
    assert completed['all_attempt_http_requests'] == len(all_calls) == 374
    semantic = sum(c.get('attempt') == 1 for c in all_calls)
    assert completed['all_attempt_semantic_requests'] == semantic == 348
    usage = {}
    for call in all_calls:
        for name, value in (call.get('usage') or {}).items():
            if isinstance(value, (int, float)):
                usage[name] = usage.get(name, 0) + value
    assert usage == summary['all_attempt_token_usage']
    secret = os.environ.get('DEEPSEEK_API_KEY')
    assert secret, 'Credential presence required for private absence audit'
    all_source_paths = [p for source in (SOURCE, FAILED) for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    assert all(secret.encode() not in p.read_bytes() for p in all_source_paths), 'Credential detected; do not archive'
    EXPORT.mkdir(parents=True)
    originals, archives = {}, {}
    copy_and_hash(SOURCE, EXPORT, 'replay_v4', originals, archives)
    copy_and_hash(FAILED, EXPORT, 'failed_v3_attempt', originals, archives)
    for version, frozen in (('v4', freeze), ('v3', read(FAILED / 'freeze.json'))):
        for rel, expected in source_files(frozen).items():
            path = ROOT / rel
            target = EXPORT / 'sources' / version / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            assert digest(target) == expected
            archives[target.relative_to(EXPORT).as_posix()] = digest(target)
    verification = dict(status='verified', episodes=160, node_periods=96000, shock_pairs=40,
        unique_demand_paths_per_type=integrity['unique_demand_paths_per_type'],
        input_replay_from_exposed_v3=True, raw_v3_failure_separately_preserved=True,
        shock_transform_checks=integrity['shock_transform_checks'],
        model_files_and_best_parameter_hashes=integrity['model_files_and_best_parameter_hashes'],
        source_protocol_input_hashes='passed', cost_backlog_period_recomputation='passed',
        normal_and_pre_notice_checks=computed['normal_and_pre_notice_checks'],
        runtime_failures=computed['runtime_failures'], api_http=len(all_calls),
        semantic_attempts=semantic, token_usage=usage, configured_credential_absent=True,
        development_only=True, independent_confirmation=False, currency_cost=None,
        progress_status_reconciled=True)
    (EXPORT / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding='utf-8')
    archives['verification.json'] = digest(EXPORT / 'verification.json')
    (EXPORT / 'export_hashes.json').write_text(json.dumps(dict(original_sha256=originals, archive_sha256=archives), indent=2), encoding='utf-8')
    print('SHOCK_TYPES_V4_ARCHIVE_VERIFIED', len(originals), 'raw files;', len(archives),
          'archive entries; no API; no credential bytes; outcomes development-only', flush=True)


if __name__ == '__main__':
    main()
