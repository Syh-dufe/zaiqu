"""Extend normal-demand HAPPO with five fixed seeds, one training job at a time."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'results/happo_seed_extension/formal_v1'
SEEDS = list(range(16, 21))
AUTHOR = ROOT / 'external/liu-inventory'
PLAN = ROOT / 'docs/superpowers/plans/2026-10-10-happo-seeds16-20.md'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temp.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def name(seed):
    return f'curve_seed{seed}_extension_v1'


def directory(seed):
    return ROOT / 'results/learning_curve' / name(seed)


def command(seed):
    return [sys.executable, '-u', str(ROOT/'experiments/learning_curve/run.py'),
            '--seed', str(seed), '--budget', '3000000', '--patience', '40',
            '--until-stable', '--run-name', name(seed)]


def verify(manifest):
    for path, expected in manifest['hashes'].items():
        assert sha(ROOT/path) == expected, f'Frozen file changed: {path}'
    for path, expected in manifest['old_models'].items():
        assert sha(Path(path)) == expected, f'Old model changed: {path}'
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=AUTHOR, text=True).strip() == manifest['author_commit']
    assert not subprocess.check_output(['git', 'diff', 'HEAD', '--name-only'], cwd=AUTHOR).strip()


def register():
    assert not OUT.exists(), 'Existing registration must be preserved'
    for seed in SEEDS:
        assert not directory(seed).exists()
        assert not (ROOT/'external/results/MyEnv/Emergency_Replenishment_Compatibility/happo'/name(seed)).exists()
    sys.path.insert(0, str(AUTHOR))
    from config import get_config
    spec = importlib.util.spec_from_file_location('extension_launcher', ROOT/'experiments/emergency_compatibility/train.py')
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    old_configs = [ROOT/f'docs/artifacts/formal_bc_v1/training/{seed}/config.json' for seed in range(11,16)]
    checks = {}
    for seed in SEEDS:
        args = launcher.seed_list_parser(get_config).parse_args([
            '--scenario_name', launcher.SCENARIO, '--experiment_name', name(seed),
            '--seed', str(seed), '--num_env_steps', '3000000', '--n_no_improvement_thres', '40'])
        new = vars(args)
        for old_path in old_configs:
            old = read(old_path)['config']
            assert set(old) == set(new)
            delta = {k: [old[k], new[k]] for k in old if old[k] != new[k]}
            assert set(delta) <= {'seed', 'experiment_name'}, delta
        checks[str(seed)] = new
    files = list(AUTHOR.rglob('*.py')) + list((AUTHOR/'test_data/test_demand_merton').glob('*'))
    files += old_configs + [Path(__file__), PLAN, ROOT/'experiments/learning_curve/run.py',
        ROOT/'experiments/emergency_compatibility/train.py', ROOT/'experiments/formal_evaluation/audit_training.py',
        ROOT/'scripts/plot_learning_curve.py']
    files = sorted(set(p for p in files if p.is_file()))
    demands = list((AUTHOR/'test_data/test_demand_merton').glob('*'))
    assert len([p for p in demands if p.is_file()]) == 20
    for path in files:
        if path.suffix == '.py':
            compile(path.read_bytes(), str(path), 'exec')
    old_models = {}
    for seed in range(11,16):
        done_path = ROOT/f'docs/artifacts/formal_bc_v1/training/{seed}/completed.json'
        files.append(done_path)
        model_dir = Path(read(done_path)['final_model_directory']).parent/'models'
        for agent in range(3):
            for label in ('actor', 'critic'):
                path = model_dir/f'{label}_agent{agent}.pt'
                old_models[str(path)] = sha(path)
    import torch
    import numpy
    manifest = dict(seeds=SEEDS, parallel_limit=1, budget_per_seed=3000000, patience=40,
        until_stable=True, training='Normal Merton only; original 20 normal validation paths',
        api_calls=0, seed_selection='All five retained, no disaster-performance selection',
        author_commit='a7e5a3e83e21565a5799483bc534e39635ec65dd',
        hashes={str(p.relative_to(ROOT)).replace('\\','/'): sha(p) for p in files},
        old_models=old_models, commands={str(seed): command(seed) for seed in SEEDS},
        python=sys.version, executable=sys.executable, torch=torch.__version__, numpy=numpy.__version__)
    verify(manifest)
    OUT.mkdir(parents=True)
    write(OUT/'manifest.json', manifest)
    write(OUT/'preflight.json', dict(passed=True, configs=checks, allowed_differences=['seed','experiment_name'],
        old_model_count=len(old_models), validation_paths=20, api_calls=0, training_steps=0))
    (OUT/'sources').mkdir()
    for path in files:
        shutil.copy2(path, OUT/'sources'/('_'.join(path.relative_to(ROOT).parts)))
    print('HAPPO_EXTENSION_REGISTERED', len(files), flush=True)


def run():
    manifest = read(OUT/'manifest.json')
    assert read(OUT/'preflight.json')['passed']
    verify(manifest)
    revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote = subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0]
    assert revision == remote, 'Push training registration before launching'
    with (OUT/'started.lock').open('x') as stream:
        stream.write(str(os.getpid()))
    started = time.time()
    write(OUT/'launch.json', dict(pid=os.getpid(),started=started,revision=revision))
    states = {str(seed): dict(status='queued') for seed in SEEDS}
    def update(seed, **data):
        states[str(seed)].update(data)
        write(OUT/'progress.json', dict(seeds=states,parallel_limit=1,started=started))
    try:
        for seed in SEEDS:
            verify(manifest)
            assert not directory(seed).exists()
            with (OUT/f'seed{seed}_train.log').open('x',encoding='utf-8') as log:
                child = subprocess.Popen(command(seed),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                update(seed,status='training',pid=child.pid)
                code = child.wait()
            assert code == 0, f'Training failed seed {seed}: {code}'
            verify(manifest)
            update(seed,status='auditing')
            with (OUT/f'seed{seed}_audit.log').open('x',encoding='utf-8') as log:
                subprocess.run([sys.executable,'-u',str(ROOT/'experiments/formal_evaluation/audit_training.py'),str(directory(seed))],
                    cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
                subprocess.run([sys.executable,str(ROOT/'scripts/plot_learning_curve.py'),str(directory(seed))],
                    cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
            verify(manifest)
            done = read(directory(seed)/'completed.json')
            update(seed,status='completed',steps=done['completed_steps'],stop_reason=done['stop_reason'],
                stable=done['stability']['stable'],official_best_cost=done['official_best_cost'])
            print('SEED_COMPLETED',seed,done['completed_steps'],flush=True)
        write(OUT/'completed.json',dict(seeds=states,wall_seconds=time.time()-started,api_calls=0))
    except Exception as exc:
        write(OUT/'failed.json',dict(error=str(exc),seeds=states,preserved=True))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['register','verify','run'])
    action = parser.parse_args().action
    if action == 'register': register()
    elif action == 'run': run()
    else: verify(read(OUT/'manifest.json'))
