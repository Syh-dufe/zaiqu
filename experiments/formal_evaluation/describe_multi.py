"""Supplement registered primary analysis with all protocol descriptive metrics."""
import csv
import gzip
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / 'docs/artifacts/formal_bc_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    target = EXPORT / 'descriptive.json'
    if target.exists():
        raise RuntimeError('Preserve existing descriptive results')
    suites = []
    episodes = []
    for directory in sorted(EXPORT.glob('stage_*_seed*_k*_v1')):
        manifest = read(directory / 'manifest.json')
        state = read(directory / 'progress.json')
        k = manifest['report_interval']
        decision_groups = {}
        for record in state['completed']:
            batch = directory / record['name']
            inputs = read(batch / 'demands.json')
            with gzip.open(batch / 'periods.csv.gz', 'rt', encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            grouped = {}
            for row in rows:
                grouped.setdefault((row['group'], row['scenario'], int(row['trace'])), []).append(row)
            for (group, scenario, trace), subset in grouped.items():
                event = inputs['events'][trace]
                lower = [r for r in subset if int(r['node']) == 0]
                active = [r for r in lower if event['start_index'] < int(r['period']) <= event['start_index'] + event['duration']]
                recovery = [r for r in lower if int(r['period']) > event['start_index'] + event['duration']]
                lo, hi = event['start_index'], event['start_index'] + event['duration']
                base = sum(inputs['base'][trace][lo:hi]); shock = sum(inputs['shock'][trace][lo:hi])
                episodes.append({'suite': directory.name, 'batch': record['name'], 'seed': read(Path(manifest['training_directory']) / 'config.json')['config']['seed'][0],
                                 'report_interval': k, 'trace': trace, 'group': group, 'scenario': scenario,
                                 'total_cost': sum(float(r['cost']) for r in subset),
                                 'mean_inventory': float(np.mean([int(r['inventory']) for r in subset])),
                                 'event_backlog': float(np.mean([int(r['backlog']) for r in active])),
                                 'recovery_backlog': float(np.mean([int(r['backlog']) for r in recovery])),
                                 'peak_downstream_backlog': max(int(r['backlog']) for r in lower),
                                 'final_downstream_backlog': int(next(r['backlog'] for r in lower if int(r['period']) == 200)),
                                 'final_inventory_total': sum(int(r['inventory']) for r in subset if int(r['period']) == 200),
                                 'actual_event_demand_ratio': shock / base if base else None,
                                 'shock_cap_count': sum(v == 20 for v in inputs['shock'][trace][lo:hi])})
            with gzip.open(batch / 'scores.json.gz', 'rt', encoding='utf-8') as stream:
                decisions = json.load(stream)
            for decision in decisions:
                group = decision.get('group', 'llm_library')
                stats = decision_groups.setdefault(group, {'decisions': 0, 'nonzero_selections': 0, 'zero_fallbacks': 0, 'screening_seconds': 0, 'forecast_absolute_error_sum': 0, 'forecast_values': 0})
                stats['decisions'] += 1
                stats['nonzero_selections'] += decision['chosen'] != 'zero'
                stats['zero_fallbacks'] += decision['chosen'] == 'zero'
                stats['screening_seconds'] += decision['seconds']
                actual = inputs['shock'][decision['trace']]
                start = decision['period'] - 1
                for paths in decision['forecasts']:
                    for path in paths:
                        for i, value in enumerate(path):
                            if start + i < 200:
                                stats['forecast_absolute_error_sum'] += abs(float(value) - actual[start+i])
                                stats['forecast_values'] += 1
        for stats in decision_groups.values():
            stats['forecast_mae_posthoc'] = stats['forecast_absolute_error_sum'] / stats['forecast_values'] if stats['forecast_values'] else None
        suites.append({'suite': directory.name, 'wall_seconds': state['wall_seconds'], 'decisions_by_group': decision_groups,
                       'no_screen_note': 'Fixed first rule has no screening decision records; missing records are not zero rule applications'})
    assert len(episodes) == 2000 and len(suites) == 20
    result = {'episodes': episodes, 'suites': suites, 'interpretation': 'Duplicate audit episodes retained but not independent samples; future demand used only for posthoc prediction error. End backlog is not a recovery time metric.',
              'development_api': {'prior_refinement_requests': 120, 'includes_failures': True, 'tokens': None,
                                  'note': 'Prior API usage predates formal frozen-library evaluation. Aggregate token/failure totals have not been independently reconstructed; unknown, not zero.'},
              'formal_api_calls': 0}
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('DESCRIBED', len(episodes), 'episodes', len(suites), 'suites')


if __name__ == '__main__':
    main()
