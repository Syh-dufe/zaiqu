"""Small paired demand shock study, using frozen policies and official evaluation."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / "external/liu-inventory"
TRAINING = ROOT / "results/learning_curve/curve_seed11_until_stable_v1"
BASE = ROOT / "results/heldout_evaluation/heldout_seed20261003_20_v1"
REVISION = "a7e5a3e83e21565a5799483bc534e39635ec65dd"


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def shock_trace(trace):
    return [min(20, math.ceil(1.5 * d)) if 80 <= i < 120 else d for i, d in enumerate(trace)]


def recovery_delay(base, shock):
    for start in range(120, 191):
        if all(shock[i] <= base[i] + 5 for i in range(start, start + 10)):
            return start - 120
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="shock_1p5_period81_120_v1")
    args_cli = parser.parse_args()
    if not args_cli.run_name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in args_cli.run_name):
        parser.error("invalid run name")
    target = ROOT / "results/demand_shock" / args_cli.run_name
    if target.exists():
        parser.error("existing output refused; select a new run name")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=UPSTREAM, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=UPSTREAM, text=True)
    if revision != REVISION or dirty.strip():
        parser.error("upstream version or tracked source changed")
    base_demands = json.loads((BASE / "demands.json").read_text())["new_traces"]
    assert len(base_demands) == 20 and all(len(t) == 201 for t in base_demands)
    shocked = [shock_trace(t) for t in base_demands]
    for a, b in zip(base_demands, shocked):
        assert a[:80] == b[:80] and a[120:] == b[120:]
        assert all(0 <= x <= 20 for x in b) and all(y >= x for x, y in zip(a, b))
    target.mkdir(parents=True)
    sys.path.insert(0, str(UPSTREAM))
    os.chdir(UPSTREAM)
    import numpy as np
    import torch
    from envs.env_wrappers import DummyVecEnv
    from runners.separated.runner import CRunner
    torch.set_num_threads(1)
    torch.manual_seed(11)
    config = json.loads((TRAINING / "config.json").read_text())["config"]
    training = json.loads((TRAINING / "completed.json").read_text())
    audit = json.loads((TRAINING / "completion_audit.json").read_text())
    previous = json.loads((BASE / "completed.json").read_text())
    model_root = Path(training["final_model_directory"]).parent
    original_total = sum(sum(t[80:120]) for t in base_demands)
    shock_total = sum(sum(t[80:120]) for t in shocked)
    demand_info = {"base_seed": 20261003, "shock_periods_inclusive": [81, 120],
        "multiplier": 1.5, "rounding": "ceil", "cap": 20,
        "window_actual_ratio": shock_total / original_total,
        "strict_cap_fraction": sum(1.5*d > 20 for t in base_demands for d in t[80:120])/800,
        "base_traces": base_demands, "shock_traces": shocked}
    write_json(target / "demands.json", demand_info)

    def parameter_hash(policies):
        digest = hashlib.sha256()
        for policy in policies:
            for network in (policy.actor, policy.critic):
                for name, tensor in network.state_dict().items():
                    digest.update(name.encode())
                    digest.update(tensor.detach().cpu().numpy().tobytes())
        return digest.hexdigest()

    class Recorder(DummyVecEnv):
        def reset(self):
            self.trace = self.env_list[0].eval_index
            return super().reset()

        def step(self, actions):
            output = super().step(actions)
            env = self.env_list[0]
            for node in range(3):
                self.rows.append({"model": self.label, "scenario": self.scenario, "trace": self.trace,
                    "period": env.step_num, "node": node, "cost": -float(output[1][0,node,0]),
                    "inventory": int(env.inventory[node]), "backlog": int(env.backlog[node]),
                    "order": int(env.current_orders[node]), "demand": int(env.get_demand()[0])})
            return output

    periods, paired, summary, checks = [], [], {}, {}
    for label, directory in (("official_best", model_root / "models"), ("final", model_root / "final_models")):
        args = argparse.Namespace(**config)
        args.model_dir = str(directory)
        envs = Recorder(args)
        runner = CRunner({"all_args": args, "envs": envs, "eval_envs": envs,
            "num_agents": 3, "device": torch.device("cpu"), "run_dir": target / label})
        before = parameter_hash(runner.policy)
        assert before == audit["model_matches"][label]["sha256"]
        scenario_rows = {}
        summary[label] = {}
        for scenario, demands in (("base", base_demands), ("shock", shocked)):
            env = envs.env_list[0]
            env.eval_data, env.n_eval, env.eval_index = demands, 20, 0
            env.record_act_sta = [[] for _ in range(3)]
            envs.rows, envs.label, envs.scenario = [], label, scenario
            reward, _ = runner.eval()
            records = envs.rows
            assert len(records) == 12000
            assert math.isclose(-float(reward), float(np.mean([r["cost"] for r in records])), abs_tol=1e-9)
            if scenario == "base":
                assert math.isclose(-float(reward), previous["summaries"][label]["new"]["mean_cost"], abs_tol=1e-9)
            scenario_rows[scenario] = records
            summary[label][scenario] = {"mean_cost": -float(reward)}
            periods.extend(records)
            print(label, scenario, -float(reward), flush=True)
        before_rows = [{k:v for k,v in r.items() if k != "scenario"}
                       for r in scenario_rows["base"] if r["period"] <= 80]
        after_rows = [{k:v for k,v in r.items() if k != "scenario"}
                      for r in scenario_rows["shock"] if r["period"] <= 80]
        assert before_rows == after_rows
        for trace in range(20):
            item = {"model": label, "trace": trace}
            curves = {}
            for scenario in ("base", "shock"):
                records = [r for r in scenario_rows[scenario] if r["trace"] == trace]
                downstream = [r for r in records if r["node"] == 0]
                assert [r["period"] for r in downstream] == list(range(1,201))
                curves[scenario] = [r["backlog"] for r in downstream]
                metrics = {"mean_cost": np.mean([r["cost"] for r in records]),
                    "shock_window_cost": np.mean([r["cost"] for r in records if 81 <= r["period"] <= 120]),
                    "downstream_peak_backlog": max(curves[scenario]),
                    "shock_window_backlog": np.mean(curves[scenario][80:120]),
                    "postshock_backlog": np.mean(curves[scenario][120:200]),
                    "terminal_backlog": curves[scenario][-1]}
                for metric, value in metrics.items():
                    item[f"{scenario}_{metric}"] = float(value)
            for metric in metrics:
                item[f"delta_{metric}"] = item[f"shock_{metric}"]-item[f"base_{metric}"]
            item["recovery_delay"] = recovery_delay(curves["base"], curves["shock"])
            item["recovery_observed"] = item["recovery_delay"] is not None
            paired.append(item)
        local = [r for r in paired if r["model"] == label]
        delays = [r["recovery_delay"] for r in local if r["recovery_observed"]]
        summary[label]["paired"] = {k:float(np.mean([r[k] for r in local]))
            for k in local[0] if k.startswith("delta_")}
        summary[label]["recovery"] = {"observed": len(delays), "right_censored": 20-len(delays),
            "observed_mean_delay": float(np.mean(delays)) if delays else None,
            "observed_max_delay": max(delays) if delays else None}
        after = parameter_hash(runner.policy)
        assert before == after
        checks[label] = {"before": before, "after": after, "unchanged": True,
            "base_reproduced": True, "pre_shock_periods_identical": True}
        runner.writter.close()
        envs.close()
    for name, rows in (("periods.csv", periods), ("paired.csv", paired)):
        with (target / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    result = {"summaries": summary, "checks": checks, "training_updates": 0,
        "demand_actual_ratio": demand_info["window_actual_ratio"],
        "strict_cap_fraction": demand_info["strict_cap_fraction"],
        "recovery_definition": "first 10-period window from period121 with shock downstream backlog <= paired base +5; delay=window start-121; null if censored",
        "limitations": "Exploratory stress check on 20 previously examined development traces, one training seed; no real disaster calibration or algorithm comparison.",
        "official_revision": revision}
    write_json(target / "completed.json", result)
    print("DEMAND_SHOCK_COMPLETED", json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
