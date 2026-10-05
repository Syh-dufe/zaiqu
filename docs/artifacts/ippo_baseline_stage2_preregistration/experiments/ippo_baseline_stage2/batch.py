"""Preregister and run five normal-demand IPPO seeds, at most two concurrently."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/ippo_baseline_stage2/formal_v1'
SEEDS = list(range(11, 16))


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def name(seed):
    return f'ippo_seed{seed}_formal_v1'


def directory(seed):
    return ROOT / 'results/ippo_learning_curve' / name(seed)


def command(seed):
    return [sys.executable, '-u', str(ROOT/'experiments/ippo_baseline/run.py'),
            '--seed', str(seed), '--budget', '3000000', '--patience', '40',
            '--until-stable', '--run-name', name(seed)]


def verify(manifest):
    for path, expected in manifest['hashes'].items():
        if digest(ROOT/path) != expected:
            raise RuntimeError(f'Frozen input/source changed: {path}')
    for path, expected in manifest['frozen_happo_models'].items():
        if digest(Path(path)) != expected:
            raise RuntimeError(f'Frozen HAPPO model changed: {path}')
    upstream = ROOT/'external/liu-inventory'
    assert subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip() == manifest['author_commit']
    assert not subprocess.check_output(['git', '-C', str(upstream), 'diff', 'HEAD', '--name-only']).strip()


def register():
    if OUT.exists():
        raise RuntimeError('Registration exists; inspect it, do not overwrite')
    for seed in SEEDS:
        if directory(seed).exists():
            raise RuntimeError(f'Seed output already exists: {seed}')
        if (ROOT/'external/results/MyEnv/Emergency_Replenishment_Compatibility/happo'/name(seed)).exists():
            raise RuntimeError(f'Author model directory already exists: {seed}')
    smoke = read(ROOT/'results/ippo_baseline_stage1/completion_audit.json')
    assert smoke['passed'] and smoke['completed_steps'] == 5000
    base = read(ROOT/'results/ippo_learning_curve/ippo_seed11_smoke5k_v1/config.json')['config']
    configs = []
    happo_models = {}
    config_checks = {}
    for seed in SEEDS:
        path = ROOT/f'docs/artifacts/formal_bc_v1/training/{seed}/config.json'
        original = read(path)['config']
        differences = {key: [original.get(key), value] for key, value in base.items() if original.get(key) != value}
        assert set(original) == set(base)
        assert set(differences) <= {'experiment_name', 'seed', 'num_env_steps', 'use_centralized_V'}
        assert original['num_env_steps'] == 3000000 and original['n_no_improvement_thres'] == 40
        assert original['n_rollout_threads'] == 5 and original['episode_length'] == 200
        assert original['use_centralized_V'] is True and base['use_centralized_V'] is False
        configs.append(path)
        metadata = ROOT/f'docs/artifacts/formal_bc_v1/training/{seed}'
        configs += [metadata/'completed.json', metadata/'completion_audit.json']
        model_dir = Path(read(metadata/'completed.json')['final_model_directory']).parent/'models'
        for agent in range(3):
            for label in ('actor', 'critic'):
                model = model_dir/f'{label}_agent{agent}.pt'
                happo_models[str(model)] = digest(model)
        config_checks[str(seed)] = differences
    upstream = ROOT/'external/liu-inventory'
    paths = list(upstream.rglob('*.py')) + list((upstream/'test_data/test_demand_merton').glob('*'))
    paths += list((ROOT/'experiments/ippo_baseline').glob('*.py')) + list(Path(__file__).parent.glob('*.py'))
    paths += configs + [ROOT/'experiments/emergency_compatibility/train.py',
                      ROOT/'scripts/plot_learning_curve.py',
                      ROOT/'docs/superpowers/plans/2026-10-05-ippo-baseline-stage2.md',
                      ROOT/'results/ippo_baseline_stage1/completion_audit.json']
    # Compile in memory: no training, subprocess or RNG-dependent operations.
    for path in paths:
        if path.suffix == '.py':
            compile(path.read_bytes(), str(path), 'exec')
    manifest = dict(actual_algorithm='ippo', internal_loader_label='happo', seeds=SEEDS,
                    parallel_limit=2, budget_per_seed=3000000, patience=40, until_stable=True,
                    reward='0.5 local + 0.5 system mean, unchanged',
                    training='Original normal Merton only; original 20 normal validation traces',
                    api_calls=0, author_commit='a7e5a3e83e21565a5799483bc534e39635ec65dd',
                    frozen_happo_models=happo_models,
                    hashes={str(p.relative_to(ROOT)).replace('\\', '/'): digest(p) for p in paths},
                    commands={str(seed): command(seed) for seed in SEEDS})
    verify(manifest)
    OUT.mkdir(parents=True)
    write(OUT/'manifest.json', manifest)
    write(OUT/'preflight.json', dict(passed=True, config_checks=config_checks, syntax_passed=True,
                                    smoke_audit_passed=True, api_calls=0, simulations=0))
    print('REGISTERED_FIVE_IPPO_SEEDS', flush=True)


def run():
    manifest = read(OUT/'manifest.json')
    assert read(OUT/'preflight.json')['passed']
    verify(manifest)
    # Permanent exclusive lock: every restart requires diagnosis and a new version.
    with (OUT/'started.lock').open('x', encoding='utf-8') as lockfile:
        lockfile.write(str(time.time()))
    started = time.time()
    write(OUT/'launch.json', dict(started_at_unix=started, pid=__import__('os').getpid(),
                                project_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
    states = {str(seed): dict(status='queued') for seed in SEEDS}
    lock = threading.Lock()
    failed = threading.Event()

    def update(seed, **record):
        with lock:
            states[str(seed)].update(record)
            write(OUT/'progress.json', dict(seeds=states, started_at_unix=started))

    def train(seed):
        try:
            if failed.is_set():
                update(seed, status='not_started_after_failure')
                return
            verify(manifest)
            if directory(seed).exists():
                raise RuntimeError('Seed output already exists')
            logfile = OUT/f'seed{seed}_train.log'
            update(seed, status='starting', command=command(seed), log=str(logfile))
            with logfile.open('x', encoding='utf-8') as log:
                process = subprocess.Popen(command(seed), cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                update(seed, status='training', pid=process.pid)
                code = process.wait()
            if code:
                raise RuntimeError(f'Training exit {code}')
            verify(manifest)
            update(seed, status='auditing')
            with (OUT/f'seed{seed}_audit.log').open('x', encoding='utf-8') as log:
                subprocess.run([sys.executable, str(Path(__file__).with_name('audit.py')), str(directory(seed))],
                               cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
                subprocess.run([sys.executable, str(ROOT/'scripts/plot_learning_curve.py'), str(directory(seed))],
                               cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
            verify(manifest)
            done = read(directory(seed)/'completed.json')
            update(seed, status='completed', steps=done['completed_steps'], stop_reason=done['stop_reason'],
                   stable=done['stability']['stable'], official_best_cost=done['official_best_cost'])
            print('SEED_COMPLETED', seed, done['completed_steps'], done['stop_reason'], flush=True)
        except Exception as exc:
            failed.set()
            update(seed, status='failed', error=str(exc))
            raise

    errors = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(train, seed): seed for seed in SEEDS}
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                errors.append(dict(seed=futures[future], error=str(exc)))
    record = dict(status='failed' if errors else 'completed', errors=errors, seeds=states,
                  wall_seconds=time.time()-started, api_calls=0)
    write(OUT/('failed.json' if errors else 'completed.json'), record)
    if errors:
        raise RuntimeError('Failure preserved; no automatic restart')
    print('FIVE_IPPO_SEEDS_COMPLETED', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--register', action='store_true')
    group.add_argument('--run', action='store_true')
    options = parser.parse_args()
    register() if options.register else run()
