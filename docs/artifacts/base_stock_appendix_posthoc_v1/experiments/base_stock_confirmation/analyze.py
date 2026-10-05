"""Independent cost audit and paired model/path bootstrap for frozen confirmation.

Base-stock has forty demand cases and no model axis. Its deterministic episode
costs are broadcast only when forming paired differences with learned methods.
This module neither runs policies nor imports the generic historical analyze.
"""
import csv
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

SEEDS = (11, 12, 13, 14, 15)
TYPES = ('single_surge', 'sustained_surge', 'double_surge', 'surge_then_drop')
RL_METHODS = ('happo', 'ippo', 'online_feedback')
BS_METHODS = ('base_stock_z02', 'base_stock_z08')
METRICS = ('shock_cost', 'shock_backlog', 'base_cost', 'base_backlog', 'cost_did', 'backlog_did')
COMPARISONS = tuple(('online_feedback', right) for right in (BS_METHODS[0], 'happo', 'ippo', BS_METHODS[1]))
BOOTSTRAP_SEED = 20271651


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def crossed(values, coverage, replicates=20000, seed=BOOTSTRAP_SEED):
    """Paired model draw shared across types; independent path draw per type.

    Separate seeded streams ensure duplicating an identical model column cannot
    change the path draws or make the path interval artificially narrower.
    """
    require(set(values) == set(TYPES), 'All four registered types are required')
    shapes = [np.asarray(values[t]).shape for t in TYPES]
    require(all(s == shapes[0] for s in shapes), 'Crossed matrices must share axes')
    require(len(shapes[0]) == 3 and shapes[0][0] == 10 and shapes[0][1] >= 1
            and shapes[0][2] == len(METRICS), 'Expected ten paths by models by metrics')
    require(0 < coverage < 1 and replicates > 0, 'Invalid bootstrap settings')
    require(all(np.isfinite(values[t]).all() for t in TYPES), 'Nonfinite paired value')
    streams = np.random.SeedSequence(seed).spawn(1 + len(TYPES))
    models = shapes[0][1]
    model_indices = np.random.default_rng(streams[0]).integers(0, models, size=(replicates, models))
    overall = np.zeros((replicates, len(METRICS)))
    by_type = {}

    def interval(draws, point):
        tail = (1 - coverage) / 2
        low, high = np.quantile(draws, [tail, 1 - tail], axis=0)
        return {metric: dict(mean=float(point[i]), low=float(low[i]), high=float(high[i]),
                             coverage=coverage, replicates=replicates)
                for i, metric in enumerate(METRICS)}

    for ti, t in enumerate(TYPES):
        a = np.asarray(values[t], dtype=float)
        paths = np.random.default_rng(streams[ti + 1]).integers(0, 10, size=(replicates, 10))
        sampled = a[paths[:, :, None], model_indices[:, None, :], :].mean(axis=(1, 2))
        overall += sampled / len(TYPES)
        by_type[t] = interval(sampled, a.mean(axis=(0, 1)))
    point = np.mean([np.asarray(values[t]).mean(axis=(0, 1)) for t in TYPES], axis=0)
    return dict(overall=interval(overall, point), by_type=by_type,
                sampling='paired model axis shared across types; ten paths independently resampled per type',
                seed=seed)


def describe(items):
    require(bool(items), 'Cannot describe empty paired results')
    return {metric: dict(mean=float(np.mean([r[metric] for r in items])), n=len(items),
                         better=sum(r[metric] < 0 for r in items),
                         tied=sum(r[metric] == 0 for r in items),
                         worse=sum(r[metric] > 0 for r in items)) for metric in METRICS}


def batch_events(entry):
    return entry['events'] if 'events' in entry else read(entry['path'])['events']


def build_comparison(rl, bs, batches, left, right):
    require(len(batches) == 10 and {int(b['batch']) for b in batches} == set(range(1, 11)),
            'Ten registered input batches are required')
    values = {t: np.full((10, len(SEEDS), len(METRICS)), np.nan) for t in TYPES}
    pairs = []
    for entry in batches:
        batch = int(entry['batch'])
        events = batch_events(entry)
        require(len(events) == 4 and {e['type'] for e in events} == set(TYPES), 'Each batch needs all four types')
        for trace, event in enumerate(events):
            for si, seed in enumerate(SEEDS):
                def episode(method, scenario):
                    key = (batch, method, scenario, trace) if method in BS_METHODS else (seed, batch, method, scenario, trace)
                    source = bs if method in BS_METHODS else rl
                    require(key in source, f'Missing paired episode: {key}')
                    return source[key]

                def delta(scenario, field):
                    value = float(episode(left, scenario)[field]) - float(episode(right, scenario)[field])
                    require(math.isfinite(value), 'Nonfinite paired episode metric')
                    return value

                sc, sb = delta('shock', 'cost'), delta('shock', 'downstream_backlog')
                bc, bb = delta('base', 'cost'), delta('base', 'downstream_backlog')
                record = dict(seed=seed, batch=batch, trace=trace, type=event['type'],
                              demand_seed=entry.get('demand_seed'), shock_cost=sc, shock_backlog=sb,
                              base_cost=bc, base_backlog=bb, cost_did=sc-bc, backlog_did=sb-bb)
                pairs.append(record)
                values[event['type']][batch-1, si, :] = [record[k] for k in METRICS]
    require(all(np.isfinite(a).all() for a in values.values()), 'Unfilled model/path matrix')
    return dict(pairs=pairs, values=values, independent_path_cases=40)


def audited_episodes(directory, methods, normal_equality=False):
    """Recompute episode summaries from every unique raw node-period.

    Detailed transition/model/information audits are independently repeated by
    the driver. Here raw data are read again to audit the statistical inputs.
    """
    directory = Path(directory)
    episodes = read(directory / 'episodes.json')
    expected = {(m, s, t) for m in methods for s in ('base', 'shock') for t in range(4)}
    keyed = {(e['group'], e['scenario'], int(e['trace'])): e for e in episodes}
    require(len(episodes) == len(keyed) == len(expected) and set(keyed) == expected,
            f'Missing or duplicate episode in {directory}')
    raw = directory / 'periods.csv.gz'
    if not raw.exists():
        raw = directory / 'periods.csv'
    opener = gzip.open if raw.suffix == '.gz' else open
    sums = {k: [0., 0., 0, 0] for k in expected}
    seen, periods, normal = set(), set(), {}
    with opener(raw, 'rt', encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            key = (row['group'], row['scenario'], int(row['trace']))
            require(key in expected, f'Unexpected raw episode {key}')
            period, node = int(row['period']), int(row['node'])
            identity = (*key, period, node)
            require(identity not in seen and node in (0, 1, 2), f'Duplicate or invalid node-period {identity}')
            seen.add(identity)
            periods.add(period)
            cost, backlog, inventory = float(row['cost']), float(row['backlog']), float(row['inventory'])
            require(all(math.isfinite(v) for v in (cost, backlog, inventory)), 'Nonfinite raw cost/state')
            require(cost == inventory + backlog, f'Raw cost differs from inventory+backlog: {identity}')
            sums[key][0] += cost
            sums[key][2] += 1
            if node == 0:
                sums[key][1] += backlog
                sums[key][3] += 1
            if normal_equality and row['scenario'] == 'base' and row['group'] in ('happo', 'online_feedback'):
                fields = ('cost', 'inventory', 'backlog', 'actual_order', 'policy_order')
                normal[row['group'], int(row['trace']), period, node] = tuple(float(row[f]) for f in fields)
    require(periods in (set(range(200)), set(range(1, 201))), 'Expected exactly 200 registered periods')
    require(len(seen) == len(expected) * 600, 'Incomplete raw node-period count')
    recomputed = {}
    for key, original in keyed.items():
        cost, backlog, count, downstream = sums[key]
        require(count == 600 and downstream == 200, f'Incomplete raw episode {key}')
        cost, backlog = cost / 600, backlog / 200
        require(math.isclose(float(original['cost']), cost, rel_tol=0, abs_tol=1e-10), f'Episode cost mismatch {key}')
        require(math.isclose(float(original['downstream_backlog']), backlog, rel_tol=0, abs_tol=1e-10), f'Episode backlog mismatch {key}')
        recomputed[key] = dict(original, cost=cost, downstream_backlog=backlog)
    if normal_equality:
        for trace in range(4):
            for period in periods:
                for node in range(3):
                    require(normal['happo', trace, period, node] == normal['online_feedback', trace, period, node],
                            'Normal HAPPO/online_feedback raw paths differ')
    return recomputed, len(seen), digest(raw)


def resources(out):
    """Include failed attempts, not just the successful child run labels."""
    files, calls, usage = [], [], Counter()
    for path in sorted((Path(out) / 'runs').rglob('calls.json')):
        records = read(path)
        require(isinstance(records, list) and all(isinstance(c, dict) for c in records), f'Invalid calls file {path}')
        require(all(type(c.get('attempt')) is int and c['attempt'] >= 1 for c in records),
                f'Missing or invalid call attempt identity in {path}')
        calls.extend(records)
        files.append(dict(path=str(path.relative_to(out)), sha256=digest(path), http_requests=len(records)))
        for call in records:
            def collect(value, prefix=''):
                if isinstance(value, dict):
                    for key, v in value.items():
                        collect(v, f'{prefix}.{key}' if prefix else key)
                elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                    usage[prefix] += value
            collect(call.get('usage'))
    semantic = sum(c.get('attempt') == 1 for c in calls)
    require(len(calls) <= 6400 and semantic <= 3200, 'Cumulative API budget exceeded')
    failures = Counter(c.get('failure_kind', 'unknown') for c in calls if c.get('status') != 'valid')
    seconds = sum(c.get('seconds', 0) for c in calls if isinstance(c.get('seconds', 0), (int, float))
                  and not isinstance(c.get('seconds', 0), bool) and math.isfinite(c.get('seconds', 0)))
    forecast = dict(score_records=0, generation_events=0, generated_paths=0, generated_path_periods=0,
                    selection_seconds=0., revision_scoring_seconds=0., event_seconds=0.,
                    generation_failures=0, revision_failures=0, selected_zero=0)
    score_files = []
    for path in sorted((Path(out) / 'runs').rglob('scores.json')):
        records = read(path)
        require(isinstance(records, list) and all(isinstance(r, dict) for r in records), f'Invalid scores file {path}')
        score_files.append(dict(path=str(path.relative_to(out)), sha256=digest(path), records=len(records)))
        for record in records:
            forecast['score_records'] += 1
            forecast['generation_events'] += record.get('generation_event') is True
            forecast['generation_failures'] += record.get('failure') == 'generation_failed'
            forecast['revision_failures'] += record.get('revision_failed') is True
            forecast['selected_zero'] += record.get('chosen') == 'zero'
            paths = record.get('forecasts', [])
            require(isinstance(paths, list) and all(isinstance(group, list) for group in paths), 'Invalid recorded forecast paths')
            for group in paths:
                require(all(isinstance(p, list) for p in group), 'Invalid recorded forecast path')
                forecast['generated_paths'] += len(group)
                forecast['generated_path_periods'] += sum(len(p) for p in group)
            for target, source in (('selection_seconds', 'seconds'), ('revision_scoring_seconds', 'revision_scoring_seconds'),
                                   ('event_seconds', 'event_seconds')):
                value = record.get(source, 0)
                require(isinstance(value, (int, float)) and not isinstance(value, bool)
                        and math.isfinite(value) and value >= 0, 'Invalid recorded scoring time')
                forecast[target] += value
    return dict(api_requests=len(calls), semantic_requests=semantic, token_usage=dict(usage),
                api_failure_kinds=dict(failures), api_seconds=seconds, call_files=files,
                forecast_resources=forecast, score_files=score_files,
                resource_time_note='Event wall time includes API/selection/revision time; these fields overlap and must not be added.',
                forecast_resource_scope='All persisted score records including failed runs; forecasts interrupted before score persistence are not recoverable.',
                calls_with_recorded_numeric_usage=sum(isinstance(c.get('usage'), dict) and any(
                    isinstance(v, (int, float)) and not isinstance(v, bool) for v in c['usage'].values()) for c in calls),
                all_attempts_included_in_resources=True, historical_api_costs_excluded=True)


def summarize(out, manifest, finished):
    """Write summary.json only; driver owns final completed/raw re-verification."""
    out = Path(out)
    batches = manifest['input_batches']
    items = list(finished.values()) if isinstance(finished, dict) else list(finished)
    require(len(items) == 50 and {(int(i['seed']), int(i['batch'])) for i in items} ==
            {(s, b) for s in SEEDS for b in range(1, 11)}, 'Exactly fifty unique model/batch runs required')
    rl, bs, runs, bs_runs = {}, {}, [], []
    node_periods = 0
    for item in sorted(items, key=lambda i: (int(i['seed']), int(i['batch']))):
        seed, batch, label = int(item['seed']), int(item['batch']), item['run_label']
        directory = out / 'runs' / label
        require(digest(directory / 'completed.json') == item['completed_sha256'], 'Completed child hash mismatch')
        episodes, count, raw_hash = audited_episodes(directory, RL_METHODS, normal_equality=True)
        for key, e in episodes.items():
            rl[seed, batch, *key] = e
        node_periods += count
        runs.append(dict(seed=seed, batch=batch, label=label, episodes=len(episodes), node_periods=count,
                         completed_sha256=item['completed_sha256'], raw_sha256=raw_hash,
                         runtime_failures=item.get('runtime_failures', [])))
    for config, method in zip(('z02', 'z08'), BS_METHODS):
        for batch in range(1, 11):
            directory = out / 'base_stock' / config / f'batch{batch:02d}'
            episodes, count, raw_hash = audited_episodes(directory, (method,))
            for key, e in episodes.items():
                require(int(e['batch']) == batch and e['type'] == batch_events(batches[batch-1])[key[2]]['type'],
                        'Base-stock episode path/type identity mismatch')
                bs[batch, *key] = e
            node_periods += count
            bs_runs.append(dict(config=config, batch=batch, episodes=len(episodes), node_periods=count,
                                completed_sha256=digest(directory / 'completed.json'), raw_sha256=raw_hash))
    require(len(rl) == 1200 and len(bs) == 160 and node_periods == 816000, 'Full episode/node-period count required')
    comparisons = {}
    for left, right in COMPARISONS:
        paired = build_comparison(rl, bs, batches, left, right)
        pairs = paired['pairs']
        coverage = .975 if right == BS_METHODS[0] else .95
        comparisons[f'{left}-minus-{right}'] = dict(left=left, right=right, descriptive=describe(pairs),
            bootstrap=crossed(paired['values'], coverage), paired_results=pairs,
            independent_path_cases=40, crossed_model_path_cells=200,
            base_stock_model_axis='deterministic same-path broadcast only' if right in BS_METHODS else None,
            by_type={t: describe([p for p in pairs if p['type'] == t]) for t in TYPES},
            by_seed={str(s): describe([p for p in pairs if p['seed'] == s]) for s in SEEDS})
    main = comparisons['online_feedback-minus-base_stock_z02']['bootstrap']['overall']['shock_cost']
    means = {}
    for method in (*RL_METHODS, *BS_METHODS):
        source = list(rl.values()) if method in RL_METHODS else list(bs.values())
        means[method] = {scenario: {field: float(np.mean([e[field] for e in source
            if e['group'] == method and e['scenario'] == scenario])) for field in ('cost', 'downstream_backlog')}
            for scenario in ('base', 'shock')}
    bs_descriptive = {}
    for method in BS_METHODS:
        cases = []
        for entry in batches:
            batch = int(entry['batch'])
            for trace, event in enumerate(batch_events(entry)):
                base, shock = bs[batch, method, 'base', trace], bs[batch, method, 'shock', trace]
                cases.append(dict(batch=batch, trace=trace, type=event['type'], base_cost=base['cost'],
                                  shock_cost=shock['cost'], cost_increase=shock['cost']-base['cost']))
        bs_descriptive[method] = dict(independent_path_cases=40, episodes=80, training_seed_axis=False,
            cases=cases, overall={k: float(np.mean([c[k] for c in cases])) for k in ('base_cost', 'shock_cost', 'cost_increase')},
            by_type={t: dict(n=10, **{k: float(np.mean([c[k] for c in cases if c['type'] == t]))
                for k in ('base_cost', 'shock_cost', 'cost_increase')}) for t in TYPES})
    profiles = []
    for entry in batches:
        data = read(entry['path'])
        for trace, event in enumerate(data['events']):
            parts = []
            for part in event['intervals']:
                start, end = part['start'], part['end']
                base, shock = data['base'][trace][start:end], data['shock'][trace][start:end]
                b, s = sum(base), sum(shock)
                parts.append(dict(**part, base_total=b, shock_total=s,
                                  actual_change_ratio=(s-b)/b if b else None,
                                  absolute_change=sum(abs(a-c) for a, c in zip(base, shock)),
                                  clipped_periods=sum(part['factor']*a > 20 for a in base)))
            profiles.append(dict(batch=entry['batch'], trace=trace, type=event['type'], intervals=parts,
                                 unchanged_consumed_path=data['base'][trace][:200] == data['shock'][trace][:200]))
    summary = dict(status='complete', phase='independent_confirmation', development_only=False,
        episodes=1360, node_periods=node_periods, rl_episodes=1200, base_stock_episodes=160,
        primary=dict(comparison='online_feedback-minus-base_stock_z02', metric='shock_cost', cost=main,
                     stronger_cost_evidence=main['mean'] < 0 and main['high'] < 0,
                     decision_uses_backlog=False), comparisons=comparisons, method_means=means,
        base_stock_descriptive=bs_descriptive, actual_profiles=profiles, runs=runs, base_stock_runs=bs_runs,
        statistics_recomputed_from_raw=True, all_registered_cases_retained=True, **resources(out),
        limitations='Five paired training seeds and forty type-specific paths. Base-stock has no training seed; '
            'its values are broadcast solely for paired model/path differences. LLM receives extra notification, '
            'global system states and forecast computation. This deployment-system comparison does not establish '
            'isolated semantic benefit, equal information, or equal compute. Secondary/type intervals are descriptive.')
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary
