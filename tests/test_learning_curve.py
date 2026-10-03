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


if __name__ == "__main__":
    unittest.main()
