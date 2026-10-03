"""Relief replenishment interpretation of the unchanged official Liu code.

Use --describe to inspect configuration without importing training dependencies.
Other arguments are forwarded to the official config parser.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "external" / "liu-inventory"
REVISION = "a7e5a3e83e21565a5799483bc534e39635ec65dd"
SCENARIO = "Emergency_Replenishment_Compatibility"


def seed_list_parser(factory):
    """Keep official defaults while making explicit seed values iterable."""
    parser = factory()
    for action in parser._actions:
        if action.dest == "seed":
            action.nargs = "+"
            break
    return parser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--run-name", default="liu_original_rules_v1")
    options, forwarded = parser.parse_known_args()
    if not options.run_name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in options.run_name):
        parser.error("--run-name must contain only letters, numbers, underscores or hyphens")
    # These names determine output paths; keep the adapter's namespace isolated.
    for token in forwarded:
        if token.split("=", 1)[0] in {"--scenario_name", "--experiment_name", "--env_name", "--algorithm_name", "--model_dir"}:
            parser.error(f"{token} is reserved by this compatibility launcher")
    if not (ORIGINAL / "train_env.py").is_file():
        parser.error(f"official checkout is missing: {ORIGINAL}")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ORIGINAL, text=True).strip()
    if revision != REVISION:
        parser.error(f"official revision differs: {revision}")
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ORIGINAL, text=True)
    if dirty.strip():
        parser.error("official tracked files have changed; restore or audit them before launching")
    output = ORIGINAL.parent / "results" / "MyEnv" / SCENARIO / "happo" / options.run_name
    official_args = ["--scenario_name", SCENARIO, "--experiment_name", options.run_name, *forwarded]
    metadata = {
        "official_revision": revision,
        "official_directory": str(ORIGINAL),
        "entrypoint_sha256": hashlib.sha256((ORIGINAL / "train_env.py").read_bytes()).hexdigest(),
        "output_directory": str(output),
        "official_arguments": official_args,
        "nodes_downstream_to_upstream": ["救援物资发放点", "区域救援仓库", "上游物资中心"],
        "mode": "business_interpretation_only",
        "demand": "unchanged official Merton generator and official evaluation files",
        "reward": "unchanged official mean-cost mixed reward",
        "python": sys.version,
        "python_executable": sys.executable,
        "cli_adapter": "explicit --seed values parsed as a list; defaults unchanged",
    }
    if options.describe:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return
    # Import only after selecting the official checkout, including on Windows spawn.
    sys.path.insert(0, str(ORIGINAL))
    import config
    official_factory = config.get_config
    config.get_config = lambda: seed_list_parser(official_factory)
    config.get_config().parse_args(official_args)  # Reject mistyped flags before creating outputs.
    if output.exists():
        parser.error(f"output already exists; choose a new --run-name to preserve results: {output}")
    output.mkdir(parents=True)
    (output / "compatibility_manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chdir(ORIGINAL)
    sys.argv = [str(ORIGINAL / "train_env.py"), *official_args]
    runpy.run_path(str(ORIGINAL / "train_env.py"), run_name="__main__")


if __name__ == "__main__":
    main()

