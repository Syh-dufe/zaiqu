"""Correctness checks authorized by the baseline development plan (no API)."""
import math
import unittest
from policy import BaseStock


class PolicyChecks(unittest.TestCase):
    def test_constant_and_population_variance(self):
        p = BaseStock(z=8)
        decision = p.decide([10]*3, [0]*3, [[10]*4]*3)
        self.assertEqual(decision[0]['variance'], 0)
        self.assertEqual(decision[0]['target'], 40)
        self.assertEqual(decision[0]['action'], 0)
        p.history[0].clear()
        p.history[0].extend([0, 20]*20)
        d = p.decide([0]*3, [0]*3, [[0]*4]*3)[0]
        self.assertEqual(d['variance'], 100)
        self.assertEqual(d['target'], 200)
        self.assertEqual(d['action'], 20)

    def test_pending_orders_count_once(self):
        p = BaseStock(z=0)
        p.observe([20, 10, 10], [20, 10, 10], [3, 10, 10])
        self.assertEqual(p.unshipped, [17, 0, 0])
        d = p.decide([2]*3, [5]*3, [[3]*4]*3)[0]
        self.assertEqual(d['position'], 26)
        self.assertEqual(d['action'], 15)

    def test_report_not_used_until_complete(self):
        p = BaseStock(z=0, information='report_mean')
        p.observe([0]*3, [0]*3, [0]*3)
        p.observe([20]*3, [0]*3, [0]*3)
        self.assertEqual(list(p.history[0]), [10]*40)
        p.observe([10]*3, [0]*3, [0]*3)
        self.assertEqual(list(p.history[0]), [10]*40)

    def test_floor_is_explicit_sensitivity(self):
        p = BaseStock(z=0, rounding='floor')
        p.history[0][-1] = 11
        self.assertEqual(p.decide([0]*3, [0]*3, [[0]*4]*3)[0]['action'], 20)
        a = BaseStock(z=0)
        a.history[0][-1] = 11
        self.assertEqual(a.decide([20]*3, [0]*3, [[0]*4]*3)[0]['action'], 20)
        self.assertEqual(p.decide([40]*3, [0]*3, [[0]*4]*3)[0]['action'], 0)
        self.assertEqual(a.decide([40]*3, [0]*3, [[0]*4]*3)[0]['action'], 1)

    def test_environment_ledger_and_causal_prefix(self):
        from batch import episode
        first = episode([10]*200, z=8)
        second = episode([10]*60+[20]*140, z=8)
        self.assertEqual(first['rows'][:180], second['rows'][:180])
        self.assertEqual(len(first['rows']), 600)
        self.assertTrue(first['ledger_verified'])
        self.assertAlmostEqual(first['cost'], sum(r['inventory']+r['backlog'] for r in first['rows'])/600)

    def test_independent_audit_rejects_changed_action(self):
        from batch import episode
        from audit import verify_episode
        result = episode([10]*200)
        verify_episode(result['rows'], [10]*200, dict(z=8))
        result['rows'][0]['action'] = 1
        with self.assertRaises(AssertionError):
            verify_episode(result['rows'], [10]*200, dict(z=8))


if __name__ == '__main__':
    unittest.main()
