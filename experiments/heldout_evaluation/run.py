"""Evaluate two preselected frozen checkpoints on fixed new Merton demands."""
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
UPSTREAM = ROOT / "external" / "liu-inventory"
REVISION = "a7e5a3e83e21565a5799483bc534e39635ec65dd"
TRAINING = ROOT / "results/learning_curve/curve_seed11_until_stable_v1"
DEMAND_SEED = 20261003
TRACE_COUNT = 20


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def demand_hash(trace):
    return hashlib.sha256(json.dumps([int(x) for x in trace[:200]]).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="heldout_seed20261003_20_v1")
    options = parser.parse_args()
    if not options.run_name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in options.run_name):
        parser.error("run name must contain only ASCII letters, digits, underscores or hyphens")
    target = ROOT / "results/heldout_evaluation" / options.run_name
    if target.exists():
        parser.error("result directory exists; use a new name to preserve prior results")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=UPSTREAM, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=UPSTREAM, text=True)
    if revision != REVISION or dirty.strip():
        parser.error("official checkout revision or tracked source differs")
    target.mkdir(parents=True)
    sys.path.insert(0, str(UPSTREAM))
    os.chdir(UPSTREAM)
    import numpy as np
    import torch
    from envs import serial, generator
    from envs.env_wrappers import DummyVecEnv
    from runners.separated.runner import CRunner
    torch.set_num_threads(1)
    torch.manual_seed(11)
    np.random.seed(DEMAND_SEED)
    original_count, original = serial.get_eval_data()
    new = [generator.merton(200, 20).demand_list for _ in range(TRACE_COUNT)]
    original_hashes = {demand_hash(trace) for trace in original}
    new_hashes = [demand_hash(trace) for trace in new]
    assert original_count == TRACE_COUNT
    assert len(set(new_hashes)) == TRACE_COUNT
    assert not original_hashes.intersection(new_hashes)
    write_json(target / "demands.json", {"seed": DEMAND_SEED, "generator": "official merton(200,20)",
        "generated_length": 201, "evaluated_periods": 200,
        "original_hashes": [demand_hash(t) for t in original],
        "new_hashes": new_hashes, "new_traces": new})
    config = json.loads((TRAINING / "config.json").read_text())["config"]
    completed = json.loads((TRAINING / "completed.json").read_text())
    audit = json.loads((TRAINING / "completion_audit.json").read_text())
    run_dir = Path(completed["final_model_directory"]).parent
    model_dirs = {"official_best": run_dir / "models", "final": run_dir / "final_models"}

    def model_hash(policies):
        digest = hashlib.sha256()
        for policy in policies:
            for network in (policy.actor, policy.critic):
                for name, tensor in network.state_dict().items():
                    digest.update(name.encode())
                    digest.update(tensor.detach().cpu().numpy().tobytes())
        return digest.hexdigest()

    class RecordingEnv(DummyVecEnv):
        def reset(self):
            self.trace_index = self.env_list[0].eval_index
            return super().reset()

        def step(self, actions):
            result = super().step(actions)
            env = self.env_list[0]
            for node in range(3):
                self.records.append({"model": self.model_label, "dataset": self.dataset_label,
                    "trace": self.trace_index, "period": env.step_num, "node": node,
                    "cost": -float(result[1][0, node, 0]),
                    "inventory": int(env.inventory[node]), "backlog": int(env.backlog[node]),
                    "order": int(env.current_orders[node]), "demand": int(env.get_demand()[0])})
            return result

    all_records, traces, summaries, hash_checks = [], [], {}, {}
    for label, directory in model_dirs.items():
        args = argparse.Namespace(**config)
        args.model_dir = str(directory)
        eval_env = RecordingEnv(args)
        runner = CRunner({"all_args": args, "envs": eval_env, "eval_envs": eval_env,
            "num_agents": 3, "device": torch.device("cpu"), "run_dir": target / label})
        before = model_hash(runner.policy)
        assert before == audit["model_matches"][label]["sha256"]
        summaries[label] = {}
        for dataset, demands in (("original", original), ("new", new)):
            env = eval_env.env_list[0]
            env.eval_data, env.n_eval, env.eval_index = demands, len(demands), 0
            env.record_act_sta = [[] for _ in range(3)]
            eval_env.records = []
            eval_env.model_label, eval_env.dataset_label = label, dataset
            # Use the author's exact deterministic evaluation loop; no training.
            reward, ordering_fluctuation = runner.eval()
            records = eval_env.records
            assert len(records) == TRACE_COUNT * 200 * 3
            assert math.isclose(-float(reward), float(np.mean([r["cost"] for r in records])), abs_tol=1e-9)
            if dataset == "original":
                expected = 23.71875 if label == "official_best" else completed["final_eval_cost"]
                assert math.isclose(-float(reward), expected, abs_tol=1e-9)
            local_traces = []
            for index in range(TRACE_COUNT):
                selected = [r for r in records if r["trace"] == index]
                assert len(selected) == 600 and {r["period"] for r in selected} == set(range(1, 201))
                item = {"model": label, "dataset": dataset, "trace": index,
                    "mean_cost": float(np.mean([r["cost"] for r in selected])),
                    "demand_mean": float(np.mean(demands[index][:200]))}
                for node in range(3):
                    node_rows = [r for r in selected if r["node"] == node]
                    for metric in ("inventory", "backlog"):
                        item[f"node{node}_{metric}_mean"] = float(np.mean([r[metric] for r in node_rows]))
                traces.append(item)
                local_traces.append(item)
            costs = [r["mean_cost"] for r in local_traces]
            summaries[label][dataset] = {"traces": TRACE_COUNT, "mean_cost": -float(reward),
                "trace_cost_sample_sd": float(np.std(costs, ddof=1)),
                "trace_cost_min": min(costs), "trace_cost_max": max(costs),
                "trace_cost_median": float(np.median(costs)),
                "ordering_fluctuation_official": [float(x) for x in ordering_fluctuation]}
            all_records.extend(records)
            print(label, dataset, json.dumps(summaries[label][dataset]), flush=True)
        after = model_hash(runner.policy)
        assert before == after
        hash_checks[label] = {"before": before, "after": after, "unchanged": True}
        runner.writter.close()
        eval_env.close()
    for name, rows in (("periods.csv", all_records), ("traces.csv", traces)):
        with (target / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    paired = [next(r["mean_cost"] for r in traces if r["model"] == "final" and r["dataset"] == "new" and r["trace"] == i)
              - next(r["mean_cost"] for r in traces if r["model"] == "official_best" and r["dataset"] == "new" and r["trace"] == i)
              for i in range(TRACE_COUNT)]
    result = {"official_revision": revision, "demand_seed": DEMAND_SEED, "summaries": summaries,
        "parameter_checks": hash_checks, "new_paired_final_minus_best": paired,
        "paired_mean": float(np.mean(paired)), "training_updates": 0,
        "dependencies": {"python": sys.version, "numpy": np.__version__, "torch": torch.__version__},
        "limitations": "20 fresh same-generator traces, one training seed, no disaster shock or algorithm baseline. Original evaluation demands influenced checkpoint selection. New demands are independently drawn; no exhaustive training-trace de-duplication log exists."}
    write_json(target / "completed.json", result)
    print("HELDOUT_EVALUATION_COMPLETED", json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
