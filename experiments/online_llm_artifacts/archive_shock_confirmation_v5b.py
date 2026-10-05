"""Independently audit and losslessly archive v5b confirmation and v5 registration failure; no API."""
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
from collections import Counter
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'results/online_llm_shock_types/confirmation_v5b'
FAILED = ROOT / 'results/online_llm_shock_types/confirmation_v5'
EXPORT = ROOT / 'docs/artifacts/online_llm_shock_confirmation_v5b'
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
        for batch in range(1, 11):
            label = f'seed{seed}_batch{batch:02d}'
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
    assert total_episodes == 800 and total_rows == 480000
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
    assert not EXPORT.exists(), 'Refuse archive overwrite'
    manifest, freeze, summary, completed, progress = [read(SOURCE / (n + '.json'))
        for n in ('manifest', 'freeze', 'summary', 'completed', 'progress')]
    assert completed['episodes'] == 800 and completed['node_periods'] == 480000
    assert progress['status'] == 'completed' and len(progress['completed_runs']) == 50
    assert digest(SOURCE / 'summary.json') == completed['summary_sha256']
    assert digest(SOURCE / 'freeze.json') == manifest['freeze_sha256']
    assert digest(SOURCE / 'collision_diagnosis.json') == manifest['collision_diagnosis_sha256']
    protocol = ROOT / 'docs/superpowers/plans/2026-10-05-independent-shock-confirmation-v5b.md'
    assert digest(protocol) == freeze['protocol_sha256']
    for relative, expected in freeze['source_sha256'].items():
        assert digest(ROOT / relative) == expected
    assert digest(ROOT / 'docs/artifacts/operator_discovery_v1/repaired_library.json') == freeze['library_sha256']
    assert digest(ROOT / 'docs/artifacts/online_llm_development_v1/inputs.json') == freeze['reference_input_sha256']
    for seed, contract in freeze['training_contracts'].items():
        for path, expected in contract['model_files'].items():
            assert digest(path) == expected
        folder = ROOT / 'results/learning_curve' / ('curve_seed11_until_stable_v1' if seed == '11' else f'curve_seed{seed}_formal_v1')
        for name, expected in contract['training_metadata'].items():
            assert digest(folder / name) == expected
        assert read(folder / 'completion_audit.json')['model_matches']['official_best']['sha256'] == contract['expected_parameter_sha256']
    collision = read(SOURCE / 'collision_diagnosis.json')
    historical = set()
    def consumed_paths(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ('base', 'shock') and isinstance(item, list):
                    for trace in item:
                        if isinstance(trace, list) and len(trace) >= 200 and all(type(x) in (int, float) for x in trace[:200]):
                            yield tuple(map(int, trace[:200]))
                else:
                    yield from consumed_paths(item)
        elif isinstance(value, list):
            for item in value:
                yield from consumed_paths(item)
    for item in collision['historical_source_manifest']:
        path = ROOT / item['path']
        assert digest(path) == item['sha256']
        historical.update(consumed_paths(read(path)))
    assert len(historical) == collision['historical_trace_count'] == 412
    new_paths, by_type, actual = set(), {}, []
    for entry in manifest['input_batches']:
        assert digest(entry['path']) == entry['sha256']
        data = read(entry['path'])
        assert entry['demand_seed'] == 20271401 + entry['batch']
        for t, event in enumerate(data['events']):
            by_type.setdefault(event['type'], set()).add(tuple(data['base'][t][:200]))
            expected = list(data['base'][t])
            for part in event['intervals']:
                for index in range(part['start'], part['end']):
                    value = data['base'][t][index] * part['factor']
                    expected[index] = min(20, math.ceil(value)) if part['factor'] > 1 else math.floor(value)
            assert expected == data['shock'][t]
            for scenario in ('base', 'shock'):
                path = tuple(data[scenario][t][:200])
                assert len(path) == 200 and path not in historical and path not in new_paths
                assert all(0 <= x <= 20 for x in path)
                new_paths.add(path)
            actual.append(dict(batch=entry['batch'], type=event['type'], intervals=event['intervals'],
                absolute_demand_change=sum(abs(a-b) for a,b in zip(data['base'][t][:200], data['shock'][t][:200]))))
    assert len(new_paths) == 80 and len(by_type) == 4 and all(len(v) == 10 for v in by_type.values())
    computed = collect_run_records(SOURCE, manifest)
    calls = computed['calls']
    semantic = sum(c.get('attempt') == 1 for c in calls)
    assert len(calls) == completed['api_requests'] == summary['api_requests'] == 1724
    assert semantic == completed['semantic_requests'] == summary['semantic_requests'] == 1569
    assert len(calls) <= manifest['first_pass_http_ceiling'] and semantic <= manifest['first_pass_semantic_ceiling']
    usage = Counter()
    for call in calls:
        for key, value in (call.get('usage') or {}).items():
            if isinstance(value, (int, float)):
                usage[key] += value
    assert dict(usage) == summary['token_usage']
    failures = Counter(c.get('failure', 'unspecified') for c in calls if c['status'] != 'valid')
    assert sum(failures.values()) == summary['api_failures'] == 189
    assert not computed['runtime_failures']
    pairs = computed['paired_results']
    assert len(pairs) == 200 and len({(p['seed'], p['batch'], p['trace']) for p in pairs}) == 200
    assert all(p['base_cost_delta'] == p['base_backlog_delta'] == 0 for p in pairs)
    # Independent calculation from period-derived outcomes, not batch.summarize.
    emap = {(e['seed'], e['batch'], e['group'], e['scenario'], e['trace']): e for e in computed['recomputed_episodes']}
    types = manifest['shock_types']
    statistics_out = {}
    for metric, field in (('cost', 'cost'), ('backlog', 'downstream_backlog')):
        cube = np.zeros((4, 10, 5))
        for ti in range(4):
            for bi in range(10):
                for si, seed in enumerate(manifest['training_seeds']):
                    cube[ti, bi, si] = emap[seed, bi+1, 'online_feedback', 'shock', ti][field] - emap[seed, bi+1, 'happo', 'shock', ti][field]
        rng = np.random.default_rng(20271003)
        samples = np.zeros((20000, 4))
        for rep in range(20000):
            models = rng.integers(0, 5, 5)
            for ti in range(4):
                paths = rng.integers(0, 10, 10)
                samples[rep, ti] = cube[ti][paths[:, None], models[None, :]].mean()
        low, high = np.quantile(samples.mean(axis=1), [.025, .975])
        registered = summary['overall']['crossed_bootstrap'][metric]['overall']
        assert np.allclose([cube.mean(), low, high], [registered['mean'], registered['ci95_low'], registered['ci95_high']], atol=1e-12, rtol=0)
        for ti, typ in enumerate(types):
            lo, hi = np.quantile(samples[:, ti], [.025, .975])
            old = summary['by_shock_type'][typ]['bootstrap'][metric]
            assert np.allclose([cube[ti].mean(), lo, hi], [old['mean'], old['ci95_low'], old['ci95_high']], atol=1e-12, rtol=0)
        # Secondary sensitivity keeps common seed/timing batch together across types.
        rng = np.random.default_rng(20271003)
        sensitivity = np.zeros(20000)
        for rep in range(20000):
            models, paths = rng.integers(0,5,5), rng.integers(0,10,10)
            sensitivity[rep] = cube[:, paths[:,None], models[None,:]].mean()
        slo, shi = np.quantile(sensitivity, [.025,.975])
        statistics_out[metric] = dict(mean=float(cube.mean()), ci95=[float(low),float(high)],
            secondary_shared_batch_ci95=[float(slo),float(shi)])
    absolute = {g: {f: statistics.mean(e[f] for e in computed['recomputed_episodes'] if e['group'] == g and e['scenario'] == 'shock')
        for f in ('cost', 'downstream_backlog')} for g in ('happo', 'online_feedback')}
    scores = [score for folder in (SOURCE / 'runs').iterdir() if folder.is_dir() for score in read(folder / 'scores.json')]
    diagnosis = dict(api_failures=dict(failures), screening_events=len(scores),
        generation_events=sum(s.get('generation_event') is True for s in scores),
        initial_generation_failures=sum(bool(s.get('failure')) for s in scores),
        feedback_generation_failures=sum(bool(s.get('revision_failed')) for s in scores),
        failed_calls_by_attempt=dict(Counter(str(c['attempt']) for c in calls if c['status'] != 'valid')),
        outcomes_by_seed={str(seed): {metric: statistics.mean(p[key] for p in pairs if p['seed'] == seed)
            for metric,key in (('cost','shock_cost_delta'),('backlog','shock_backlog_delta'))} for seed in manifest['training_seeds']})
    secret = os.environ.get('DEEPSEEK_API_KEY')
    assert secret, 'Private credential absence audit requires configured key'
    for parent in (SOURCE, FAILED):
        assert all(secret.encode() not in p.read_bytes() for p in parent.rglob('*') if p.is_file())
    EXPORT.mkdir(parents=True)
    originals, archives = {}, {}
    copy_and_hash(SOURCE, EXPORT, 'confirmation_v5b', originals, archives)
    copy_and_hash(FAILED, EXPORT, 'failed_v5_registration', originals, archives)
    for version, frozen in (('v5b', freeze), ('v5', read(FAILED / 'freeze.json'))):
        for relative, expected in frozen['source_sha256'].items():
            target = EXPORT / 'sources' / version / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
            assert digest(target) == expected
            archives[target.relative_to(EXPORT).as_posix()] = digest(target)
    for name in ('2026-10-05-independent-shock-confirmation-v5b.md', '2026-10-05-independent-shock-confirmation-v5.md'):
        target = EXPORT / 'protocols' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'docs/superpowers/plans' / name, target)
        archives[target.relative_to(EXPORT).as_posix()] = digest(target)
    verification = dict(status='verified', episodes=800, node_periods=480000, paired_cases=200,
        independently_recomputed_statistics=statistics_out, absolute_shocked_means=absolute,
        independent_collision_screen=dict(historical_paths=412, new_paths=80, exact_collisions=0),
        normal_and_pre_notice_checks=computed['normal_and_pre_notice_checks'],
        source_model_input_protocol_hashes='passed', cost_backlog_period_recomputation='passed',
        api_http=len(calls), semantic_requests=semantic, token_usage=dict(usage), diagnosis=diagnosis,
        runtime_failures=computed['runtime_failures'], credential_absent=True,
        independent_confirmation=True, development_only=False, failed_v5_registration_preserved=True)
    (EXPORT / 'verification.json').write_text(json.dumps(verification, indent=2), encoding='utf-8')
    archives['verification.json'] = digest(EXPORT / 'verification.json')
    (EXPORT / 'export_hashes.json').write_text(json.dumps(dict(original_sha256=originals, archive_sha256=archives), indent=2), encoding='utf-8')
    print(json.dumps(verification, indent=2))
    print('V5B_AUDIT_ARCHIVE_VERIFIED', len(originals), len(archives), flush=True)


if __name__ == '__main__':
    main()


