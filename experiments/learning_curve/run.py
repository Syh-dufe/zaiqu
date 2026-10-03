"""Observe the unchanged official training loop with a larger fixed budget."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import runpy
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / "external" / "liu-inventory"


def training_arguments(seed, budget, run_name):
    if budget <= 0 or budget % 1000:
        raise ValueError("budget must be a positive multiple of the official 1000-step rollout")
    return ["--run-name", run_name, "--seed", str(seed), "--num_env_steps", str(budget)]


def best_scheduled_evaluation(rows, stopped_at_plateau=False):
    if stopped_at_plateau:
        rows = rows[:-1]  # Plateau exception fires before the official save branch.
    scheduled = [row for row in rows if row["phase"] == "evaluation" and row["step"] > 0]
    return min(scheduled, key=lambda row: row["mean_actor_period_cost"], default=None)


def stability_report(costs, steps):
    """Predeclared empirical plateau rule; not a mathematical convergence proof."""
    report = {"stable": False, "steps": steps, "minimum_steps": 100000,
              "window": 10, "median_change_limit": 0.01, "recent_cv_limit": 0.05,
              "best_change_limit": 0.01}
    if steps < 100000 or len(costs) < 20:
        return report
    previous, recent = costs[-20:-10], costs[-10:]
    denominator = max(abs(statistics.median(previous)), 1e-8)
    median_change = abs(statistics.median(recent)-statistics.median(previous))/denominator
    best_change = abs(min(recent)-min(previous))/max(abs(min(previous)), 1e-8)
    cv = statistics.pstdev(recent)/max(abs(statistics.mean(recent)), 1e-8)
    report.update(median_change=median_change, best_change=best_change, recent_cv=cv)
    report["stable"] = median_change <= 0.01 and best_change <= 0.01 and cv <= 0.05
    return report


class EmpiricalPlateau(Exception):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--budget", type=int, default=50000)
    parser.add_argument("--run-name", default="curve_seed11_50k_v1")
    parser.add_argument("--until-stable", action="store_true")
    parser.add_argument("--patience", type=int, default=10)
    options = parser.parse_args()
    arguments = training_arguments(options.seed, options.budget, options.run_name)
    if options.patience < 1:
        parser.error("patience must be positive")
    if options.patience != 10:
        arguments.extend(["--n_no_improvement_thres", str(options.patience)])
    target = ROOT / "results" / "learning_curve" / options.run_name
    if target.exists():
        parser.error(f"results already exist; use a new run name: {target}")
    sys.path.insert(0, str(UPSTREAM))
    import numpy as np
    import torch
    import runners.separated.runner as runner_module
    original_runner = runner_module.CRunner
    target.mkdir(parents=True)
    rows = []
    snapshots = []

    def record(step, phase, cost):
        rows.append({"step": step, "phase": phase, "mean_actor_period_cost": float(cost)})
        with (target / "curve.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    class ObservedRunner(original_runner):
        def __init__(self, runner_config):
            runner_module.Runner.__init__(self, runner_config)
            self.completed_steps = 0
            self.check_plateau = options.until_stable
            (target / "config.json").write_text(json.dumps({
                "config": vars(self.all_args), "python": sys.version,
                "torch": torch.__version__, "numpy": np.__version__,
                "changes": "seed and budget; naming; passive curve recording and extra snapshots",
                "early_stop": {"patience": options.patience, "until_stable": options.until_stable},
            }, indent=2), encoding="utf-8")

        def train(self):
            # Read-only observations around the original update; no RNG calls.
            cost = -float(np.mean([np.mean(buffer.rewards) for buffer in self.buffer]))
            result = super().train()
            self.completed_steps += self.episode_length * self.n_rollout_threads
            # Averaging the original local+mean mixture over agents equals
            # averaging raw local rewards, so this is a training cost measure.
            record(self.completed_steps, "training", cost)
            if self.completed_steps % 5000 == 0:
                previous_dir = self.save_dir
                self.save_dir = str(self.run_dir / "curve_snapshots" / f"step_{self.completed_steps}")
                Path(self.save_dir).mkdir(parents=True)
                self.save()
                digest = hashlib.sha256()
                for policy in self.policy:
                    for network in (policy.actor, policy.critic):
                        for name, tensor in network.state_dict().items():
                            digest.update(name.encode())
                            digest.update(tensor.detach().cpu().numpy().tobytes())
                snapshots.append({"step": self.completed_steps, "directory": self.save_dir,
                                  "parameter_sha256": digest.hexdigest()})
                self.save_dir = previous_dir
                (target / "snapshots.json").write_text(json.dumps(snapshots, indent=2), encoding="utf-8")
            return result

        def eval(self):
            result = super().eval()
            record(self.completed_steps, "evaluation", -float(result[0]))
            costs = [row["mean_actor_period_cost"] for row in rows
                     if row["phase"] == "evaluation" and row["step"] > 0]
            report = stability_report(costs, self.completed_steps)
            (target / "stability.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            if self.check_plateau and report["stable"]:
                raise EmpiricalPlateau()
            return result

        def run(self):
            original_result = None
            stop_reason = "budget"
            try:
                original_result = super().run()
                if original_result is not None:
                    stop_reason = "official_early_stop"
            except EmpiricalPlateau:
                stop_reason = "empirical_plateau"
            self.check_plateau = False
            scheduled_best = best_scheduled_evaluation(rows, stop_reason == "empirical_plateau")
            # Budget-boundary handling only; final policy is not the best model.
            final_reward, bw = self.eval()
            final_dir = self.run_dir / "final_models"
            final_dir.mkdir()
            old_dir = self.save_dir
            self.save_dir = str(final_dir)
            self.save()
            self.save_dir = old_dir
            from algorithms.happo_policy import HAPPO_Policy
            max_error = 0.0
            for index, policy in enumerate(self.policy):
                loaded = HAPPO_Policy(self.all_args, self.envs.observation_space[index],
                                     self.envs.share_observation_space[index],
                                     self.envs.action_space[index], device=self.device)
                for label in ("actor", "critic"):
                    state = torch.load(final_dir / f"{label}_agent{index}.pt",
                                       map_location=self.device, weights_only=True)
                    getattr(loaded, label).load_state_dict(state)
                    for name, tensor in getattr(policy, label).state_dict().items():
                        max_error = max(max_error, float(torch.max(torch.abs(
                            tensor - getattr(loaded, label).state_dict()[name]))))
            evaluations = [row for row in rows if row["phase"] == "evaluation"]
            summary = {
                "seed": options.seed, "requested_budget": options.budget,
                "completed_steps": self.completed_steps,
                "stop_reason": stop_reason,
                "initial_eval_cost": evaluations[0]["mean_actor_period_cost"],
                "final_eval_cost": -float(final_reward),
                "best_observed_evaluation": min(evaluations, key=lambda row: row["mean_actor_period_cost"]),
                "official_best_cost": None if scheduled_best is None else scheduled_best["mean_actor_period_cost"],
                "best_scheduled_evaluation": scheduled_best,
                "final_model_directory": str(final_dir), "max_reload_error": max_error,
                "eval_traces": self.eval_envs.get_eval_num(),
                "interpretation": "single-seed learning observation, not convergence or superiority evidence",
                "stability": stability_report([row["mean_actor_period_cost"]
                    for row in evaluations[:-1] if row["step"] > 0], self.completed_steps),
            }
            (target / "completed.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print("LEARNING_CURVE_COMPLETED " + json.dumps(summary), flush=True)
            return (final_reward, bw) if original_result is None else original_result

    runner_module.CRunner = ObservedRunner
    launcher = ROOT / "experiments" / "emergency_compatibility" / "train.py"
    sys.argv = [str(launcher), *arguments]
    runpy.run_path(str(launcher), run_name="__main__")


if __name__ == "__main__":
    main()
