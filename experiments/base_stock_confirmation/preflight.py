"""No-network tests and exposed-input interface proof for formal confirmation."""
import importlib.util
import copy
import tempfile
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load_driver():
    path = Path(__file__).with_name('batch.py')
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('base_stock_confirmation_driver', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.driver = load_driver()

    def test_formal_configuration_and_counts(self):
        self.assertIsNotNone(self.driver, 'formal confirmation driver is missing')
        self.assertEqual(self.driver.CANDIDATE_SEEDS, tuple(range(20271601, 20271651)))
        self.assertEqual([c['z'] for c in self.driver.BASE_STOCK_CONFIGS], [2, 8])
        self.assertEqual(self.driver.EXPECTED_EPISODES, 1360)
        self.assertEqual(self.driver.EXPECTED_ROWS, 816000)

    def test_duplicate_screen_allows_only_same_pair(self):
        self.assertIsNotNone(self.driver, 'formal confirmation driver is missing')
        records = [(0, 'base', (1,)), (0, 'shock', (1,)), (1, 'base', (2,))]
        collisions, equal = self.driver.screen_paths(records, set(), set())
        self.assertEqual(collisions, [])
        self.assertEqual(equal, [0])
        collisions, _ = self.driver.screen_paths(records + [(1, 'shock', (1,))], set(), set())
        self.assertTrue(collisions)
        self.assertTrue(self.driver.screen_paths(records, {(1,)}, set())[0])

    def test_audit_import_is_rebound_after_other_module(self):
        self.assertIsNotNone(self.driver, 'formal confirmation driver is missing')
        driver = self.driver
        sys.modules['analyze'] = object()
        driver.bind_legacy_audit()
        self.assertIs(sys.modules['analyze'], driver.a)

    def test_budget_counts_failed_requests_and_limits_full_task(self):
        self.assertIsNotNone(self.driver, 'formal confirmation driver is missing')
        self.assertTrue(hasattr(self.driver, 'check_budget'), 'budget guard is missing')
        calls=[dict(run='failed_task', attempt=1) for _ in range(1569)]
        with self.assertRaises(RuntimeError):
            self.driver.check_budget(calls, retry=0)
        calls=[dict(run='task_quota_recovery1', attempt=2) for _ in range(6337)]
        with self.assertRaises(RuntimeError):
            self.driver.check_budget(calls, retry=1)
        self.driver.check_budget([], retry=0)

    def test_independent_scalar_audit_rejects_changed_action(self):
        self.assertIsNotNone(self.driver, 'formal confirmation driver is missing')
        config=self.driver.BASE_STOCK_CONFIGS[0]
        result=self.driver.bs.episode([10]*200, **{k:v for k,v in config.items() if k!='name'})
        self.driver.diagnosis.verify_episode(result['rows'],[10]*200,config)
        altered=copy.deepcopy(result['rows'])
        altered[0]['action'] += 1
        with self.assertRaises(AssertionError):
            self.driver.diagnosis.verify_episode(altered,[10]*200,config)

    def test_call_ledger_rejects_missing_attempt_and_corrupt_or_missing_file(self):
        self.assertIsNotNone(self.driver, 'formal confirmation driver is missing')
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            folder=out/'runs'/'seed11_batch01'
            folder.mkdir(parents=True)
            with self.assertRaises(RuntimeError):
                self.driver.recorded_calls(out)
            (folder/'calls.json').write_text('broken JSON',encoding='utf-8')
            with self.assertRaises(RuntimeError):
                self.driver.recorded_calls(out)
            (folder/'calls.json').write_text(json.dumps([dict(group='online_feedback',scenario='shock')]),encoding='utf-8')
            with self.assertRaises(RuntimeError):
                self.driver.recorded_calls(out)


if __name__ == '__main__':
    if '--proof' in sys.argv:
        load_driver().no_api_proof()
    else:
        unittest.main()
