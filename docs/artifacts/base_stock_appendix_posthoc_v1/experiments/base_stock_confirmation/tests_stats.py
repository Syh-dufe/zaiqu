"""Synthetic statistical-contract tests; no API or demand generation."""
import importlib.util
import csv
import gzip
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

SPEC = importlib.util.spec_from_file_location('base_stock_confirmation_analysis', Path(__file__).with_name('analyze.py'))
analysis = importlib.util.module_from_spec(SPEC) if SPEC.loader and SPEC.origin and Path(SPEC.origin).exists() else None
if analysis is not None:
    SPEC.loader.exec_module(analysis)


class StatisticsContract(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(analysis, 'new statistical implementation is required')

    def values(self, value, models=5):
        return {t: np.full((10, models, 6), value, dtype=float) for t in analysis.TYPES}

    def fixture(self):
        rl, bs, batches = {}, {}, []
        for batch in range(1, 11):
            batches.append({'batch': batch, 'events': [{'type': t} for t in analysis.TYPES]})
            for trace, t in enumerate(analysis.TYPES):
                for scenario in ('base', 'shock'):
                    bs[batch, 'base_stock_z02', scenario, trace] = {'cost': batch * 2., 'downstream_backlog': 1.}
                    for seed in analysis.SEEDS:
                        rl[seed, batch, 'online_feedback', scenario, trace] = {'cost': batch * 2. - 3., 'downstream_backlog': 0.}
        return rl, bs, batches

    def test_bs_broadcast_does_not_create_independent_paths(self):
        rl, bs, batches = self.fixture()
        result = analysis.build_comparison(rl, bs, batches, 'online_feedback', 'base_stock_z02')
        self.assertEqual(len(bs), 80)
        self.assertEqual(len(result['pairs']), 200)
        self.assertEqual(result['independent_path_cases'], 40)
        for matrix in result['values'].values():
            np.testing.assert_array_equal(matrix[:, :, 0], -3.)

    def test_zero_constant_difference_interval_zero(self):
        result = analysis.crossed(self.values(0.), .975, replicates=101)
        self.assertEqual(result['overall']['shock_cost']['low'], 0.)
        self.assertEqual(result['overall']['shock_cost']['high'], 0.)

    def test_negative_constant_has_strict_negative_interval(self):
        result = analysis.crossed(self.values(-2.), .975, replicates=101)
        self.assertEqual(result['overall']['shock_cost']['mean'], -2.)
        self.assertEqual(result['overall']['shock_cost']['high'], -2.)

    def test_duplicate_model_axis_does_not_gain_path_precision(self):
        one = {t: np.repeat(np.arange(10.)[:, None, None], 6, axis=2) for t in analysis.TYPES}
        five = {t: np.repeat(v, 5, axis=1) for t, v in one.items()}
        self.assertEqual(analysis.crossed(one, .975, replicates=1001), analysis.crossed(five, .975, replicates=1001))

    def test_multiple_types_retain_unfavorable_results(self):
        values = self.values(-1.)
        values[analysis.TYPES[-1]][:] = 4.
        result = analysis.crossed(values, .975, replicates=101)
        self.assertEqual(set(result['by_type']), set(analysis.TYPES))
        self.assertEqual(result['by_type'][analysis.TYPES[-1]]['shock_cost']['mean'], 4.)
        self.assertEqual(result['overall']['shock_cost']['mean'], .25)

    def test_missing_pair_rejected(self):
        rl, bs, batches = self.fixture()
        del bs[1, 'base_stock_z02', 'shock', 0]
        with self.assertRaisesRegex(ValueError, 'Missing paired episode'):
            analysis.build_comparison(rl, bs, batches, 'online_feedback', 'base_stock_z02')

    def test_failed_attempt_usage_retained_only_numeric_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for label, calls in [('failed', [{'attempt': 1, 'status': 'failed', 'failure_kind': 'format',
                'usage': {'prompt_tokens': 10, 'total_tokens': '11', 'details': {'cached': 2}, 'boolean': True}}]),
                ('success', [{'attempt': 2, 'status': 'valid', 'usage': {'prompt_tokens': 3}}])]:
                folder = root / 'runs' / label
                folder.mkdir(parents=True)
                (folder / 'calls.json').write_text(json.dumps(calls), encoding='utf-8')
            result = analysis.resources(root)
            self.assertEqual(result['api_requests'], 2)
            self.assertEqual(result['semantic_requests'], 1)
            self.assertEqual(result['token_usage'], {'prompt_tokens': 13, 'details.cached': 2})
            self.assertEqual(result['api_failure_kinds'], {'format': 1})

    def test_malformed_calls_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'runs' / 'failed'
            folder.mkdir(parents=True)
            (folder / 'calls.json').write_text('{broken', encoding='utf-8')
            with self.assertRaises(ValueError):
                analysis.resources(Path(temp))

    def test_missing_attempt_identity_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'runs' / 'failed'
            folder.mkdir(parents=True)
            (folder / 'calls.json').write_text('[{"status":"failed"}]', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'attempt identity'):
                analysis.resources(Path(temp))

    def test_forecast_resource_records_include_failed_run(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / 'runs' / 'failed'
            folder.mkdir(parents=True)
            (folder / 'scores.json').write_text(json.dumps([{'generation_event': True,
                'forecasts': [[[10] * 20] * 3, [[10] * 20] * 3], 'seconds': 2.,
                'revision_scoring_seconds': 1., 'event_seconds': 5., 'failure': 'generation_failed',
                'revision_failed': True, 'chosen': 'zero'}]), encoding='utf-8')
            result = analysis.resources(Path(temp))
            self.assertEqual(result['forecast_resources']['generated_paths'], 6)
            self.assertEqual(result['forecast_resources']['generated_path_periods'], 120)
            self.assertEqual(result['forecast_resources']['selection_seconds'], 2.)
            self.assertEqual(result['forecast_resources']['generation_failures'], 1)

    def test_raw_cost_recomputed_and_tampered_episode_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            method = 'base_stock_z02'
            episodes = [{'group': method, 'scenario': scenario, 'trace': trace, 'cost': 3.,
                         'downstream_backlog': 1.} for scenario in ('base', 'shock') for trace in range(4)]
            (root / 'episodes.json').write_text(json.dumps(episodes), encoding='utf-8')
            with gzip.open(root / 'periods.csv.gz', 'wt', encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=['group', 'scenario', 'trace', 'period', 'node', 'cost', 'inventory', 'backlog'])
                writer.writeheader()
                for e in episodes:
                    for period in range(200):
                        for node in range(3):
                            writer.writerow({k: e[k] for k in ('group', 'scenario', 'trace')} |
                                            {'period': period, 'node': node, 'cost': 3, 'inventory': 2, 'backlog': 1})
            audited, count, _ = analysis.audited_episodes(root, (method,))
            self.assertEqual(count, 4800)
            self.assertEqual(audited[method, 'shock', 0]['cost'], 3.)
            episodes[0]['cost'] = 4.
            (root / 'episodes.json').write_text(json.dumps(episodes), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Episode cost mismatch'):
                analysis.audited_episodes(root, (method,))


if __name__ == '__main__':
    unittest.main()
