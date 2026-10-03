"""Compare reference and compatibility entrypoints without editing Liu source.

The audit-only runner saves and evaluates the final policy after the official
budget loop, whose normal completion has no return statement. It is not the
official best-checkpoint selection procedure.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "external" / "liu-inventory"
AUDIT = ROOT / "results" / "compatibility_verification_v2"
RUN_NAME = "audit_seed11_steps5000_v2"


def worker(mode):
    import numpy as np
    import torch
    sys.path.insert(0, str(UPSTREAM))
    os.chdir(UPSTREAM)
    import config
    import envs.serial as serial
    import runners.separated.runner as runner_module
    official_factory = config.get_config
    original_runner = runner_module.CRunner
    original_reset = serial.Env.reset
    demand_hash = hashlib.sha256()
    action_hash = hashlib.sha256()

    def observed_reset(self, *args, **kwargs):
        obs = original_reset(self, *args, **kwargs)
        demand_hash.update(json.dumps({"train": self.train, "demand": list(self.demand_list)},
                                     sort_keys=True).encode())
        return obs

    serial.Env.reset = observed_reset

    class AuditedRunner(original_runner):
        def __init__(self, runner_config):
            # The official constructor uses super(CRunner, self). Rebinding
            # that module name to a subclass would recursively call it.
            runner_module.Runner.__init__(self, runner_config)

        def collect(self, step):
            result = super().collect(step)
            action_hash.update(np.asarray(result[1]).tobytes())
            return result

        def run(self):
            defaults = vars(official_factory().parse_args([]))
            actual = vars(self.all_args)
            allowed = {"seed", "num_env_steps", "scenario_name", "experiment_name"}
            unexpected = {key: value for key, value in actual.items()
                          if key not in allowed and defaults[key] != value}
            if unexpected:
                raise AssertionError(f"Unexpected default overrides: {unexpected}")
            result = super().run()
            # Both entrypoints use identical audit-only completion handling.
            # Final actor/critic files are separate from officially selected models.
            self.save_dir = str(self.run_dir / "audit_final_models")
            Path(self.save_dir).mkdir()
            self.save()
            parameter_hash = hashlib.sha256()
            for policy in self.policy:
                for network in (policy.actor, policy.critic):
                    for name, tensor in network.state_dict().items():
                        parameter_hash.update(name.encode())
                        parameter_hash.update(tensor.detach().cpu().numpy().tobytes())
            reward, bw = self.eval()
            # Check that the final policy loads in newly initialized policies.
            from algorithms.happo_policy import HAPPO_Policy
            max_reload_error = 0.0
            for index, policy in enumerate(self.policy):
                loaded = HAPPO_Policy(self.all_args, self.envs.observation_space[index],
                                     self.envs.share_observation_space[index],
                                     self.envs.action_space[index], device=self.device)
                for label in ("actor", "critic"):
                    state = torch.load(Path(self.save_dir) / f"{label}_agent{index}.pt",
                                       map_location=self.device, weights_only=True)
                    getattr(loaded, label).load_state_dict(state)
                    for name, tensor in getattr(policy, label).state_dict().items():
                        error = float(torch.max(torch.abs(tensor - getattr(loaded, label).state_dict()[name])))
                        max_reload_error = max(max_reload_error, error)
            record = {
                "mode": mode, "budget": actual["num_env_steps"], "seeds": actual["seed"],
                "rollouts": actual["n_rollout_threads"], "horizon": actual["episode_length"],
                "demand_sha256": demand_hash.hexdigest(), "action_sha256": action_hash.hexdigest(),
                "parameter_sha256": parameter_hash.hexdigest(), "max_reload_error": max_reload_error,
                "final_eval_mean_actor_period_cost": -float(reward), "order_cv": list(bw),
                "model_directory": self.save_dir, "unexpected_default_overrides": unexpected,
                "original_budget_returned_none": result is None,
                "checkpoint_kind": "audit_final_policy_not_official_best",
                "python": sys.version, "torch": torch.__version__, "numpy": np.__version__,
            }
            (AUDIT / f"{mode}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            return (reward, bw) if result is None else result

    runner_module.CRunner = AuditedRunner
    if mode == "reference":
        def reference_factory():
            parser = official_factory()
            parser.set_defaults(seed=[11], num_env_steps=5000,
                                experiment_name=RUN_NAME + "_reference")
            return parser
        config.get_config = reference_factory
        sys.argv = [str(UPSTREAM / "train_env.py")]
        runpy.run_path(str(UPSTREAM / "train_env.py"), run_name="__main__")
    else:
        launcher = ROOT / "experiments" / "emergency_compatibility" / "train.py"
        sys.argv = [str(launcher), "--run-name", RUN_NAME + "_compatibility",
                    "--seed", "11", "--num_env_steps", "5000"]
        runpy.run_path(str(launcher), run_name="__main__")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=["reference", "compatibility"])
    options = parser.parse_args()
    if options.worker:
        worker(options.worker)
        return
    if AUDIT.exists():
        raise SystemExit(f"Audit directory already exists; preserve and review it: {AUDIT}")
    AUDIT.mkdir(parents=True)
    for mode in ("reference", "compatibility"):
        with (AUDIT / f"{mode}.log").open("w", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-u", str(Path(__file__).resolve()), "--worker", mode],
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        print(f"Completed {mode} audit", flush=True)
    reference = json.loads((AUDIT / "reference.json").read_text())
    compatibility = json.loads((AUDIT / "compatibility.json").read_text())
    fields = ["budget", "seeds", "rollouts", "horizon", "demand_sha256", "action_sha256",
              "parameter_sha256", "final_eval_mean_actor_period_cost", "order_cv"]
    comparisons = {field: reference[field] == compatibility[field] for field in fields}
    report = {"comparisons": comparisons,
              "reload_exact": reference["max_reload_error"] == compatibility["max_reload_error"] == 0,
              "scope": "one seed, 5000 transitions, same dependencies, audit-only final checkpoint"}
    log_rows = {}
    for mode in ("reference", "compatibility"):
        log_rows[mode] = [line for line in (AUDIT / f"{mode}.log").read_text(encoding="utf-8").splitlines()
                          if line.startswith("Reward for thread ")]
    report["logged_reward_inventory_order_rows_identical"] = log_rows["reference"] == log_rows["compatibility"]
    report["logged_rows_compared"] = len(log_rows["reference"])
    report["passed"] = (all(comparisons.values()) and report["reload_exact"]
                        and report["logged_reward_inventory_order_rows_identical"])
    (AUDIT / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
