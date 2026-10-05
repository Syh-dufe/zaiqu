"""Appendix invariants; no inputs, RL evaluation or API calls."""
import importlib.util
from pathlib import Path
import sys
import unittest


class AppendixTests(unittest.TestCase):
    def setUp(self):
        path=Path(__file__).with_name('batch.py')
        self.module=None
        if path.exists():
            spec=importlib.util.spec_from_file_location('appendix_test_driver',path)
            self.module=importlib.util.module_from_spec(spec)
            sys.modules[spec.name]=self.module
            spec.loader.exec_module(self.module)

    def test_use_completed_original_label_including_recharge(self):
        self.assertIsNotNone(self.module,'appendix driver missing')
        rows=[dict(seed=seed,batch=batch,label=f'seed{seed}_batch{batch:02d}',completed_sha256='hash')
              for seed in range(11,16) for batch in range(1,11)]
        rows[41]['label']='seed15_batch02_quota_recovery_recharge1'
        finished=self.module.finished_from_summary(dict(runs=rows))
        self.assertEqual(finished['seed15_batch02']['run_label'],'seed15_batch02_quota_recovery_recharge1')
        with self.assertRaises(ValueError):
            self.module.finished_from_summary(dict(runs=rows[:-1]+[rows[0]]))

    def test_posthoc_summary_never_claims_new_api_or_prospective_support(self):
        self.assertIsNotNone(self.module,'appendix driver missing')
        summary=dict(phase='independent_confirmation',api_requests=1713,semantic_requests=1583,
                     historical_api_costs_excluded=True,primary=dict(stronger_cost_evidence=True))
        result=self.module.posthoc_summary(summary)
        self.assertEqual(result['api_requests'],0)
        self.assertEqual(result['historical_api_requests'],1713)
        self.assertEqual(result['phase'],'posthoc_additional_baseline_comparison')
        self.assertFalse(result['prospective_independent_confirmation'])
        self.assertNotIn('stronger_cost_evidence',result['primary'])


if __name__=='__main__':unittest.main()
