import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("learning", ROOT / "experiments/learning_curve/run.py")


class LearningBudget(unittest.TestCase):
    def test_budget_seed_and_namespace_only(self):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.training_arguments(11, 50000, "curve_seed11_50k_v1"),
                         ["--run-name", "curve_seed11_50k_v1", "--seed", "11", "--num_env_steps", "50000"])

    def test_partial_rollout_budget_rejected(self):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(ValueError):
            module.training_arguments(11, 50100, "bad")

    def test_best_scheduled_excludes_initial_evaluation(self):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows = [{"step": 0, "phase": "evaluation", "mean_actor_period_cost": 1.0},
                {"step": 5000, "phase": "evaluation", "mean_actor_period_cost": 9.0},
                {"step": 6000, "phase": "training", "mean_actor_period_cost": 2.0}]
        self.assertEqual(module.best_scheduled_evaluation(rows)["step"], 5000)

    def test_no_scheduled_model_is_none(self):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIsNone(module.best_scheduled_evaluation([]))

    def test_plateau_trigger_precedes_official_checkpoint_save(self):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows = [{"step": 5000, "phase": "evaluation", "mean_actor_period_cost": 9.0},
                {"step": 10000, "phase": "evaluation", "mean_actor_period_cost": 8.0}]
        self.assertEqual(module.best_scheduled_evaluation(rows, stopped_at_plateau=True)["step"], 5000)

    def test_stability_requires_enough_training(self):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(module.stability_report([10.0]*20, 50000)["stable"])

    def test_flat_curve_is_stable(self):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(module.stability_report([10.0]*20, 100000)["stable"])

    def test_improving_or_noisy_curve_is_not_stable(self):
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(module.stability_report([20.0]*10+[10.0]*10, 100000)["stable"])
        self.assertFalse(module.stability_report([10.0]*10+[5.0,15.0]*5, 100000)["stable"])


if __name__ == "__main__":
    unittest.main()
