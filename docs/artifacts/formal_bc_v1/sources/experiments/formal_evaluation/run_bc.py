"""Execute registered B/C suites, retaining all seeds and refusing overwrites."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    out = ROOT / 'results/formal_evaluation/bc_pipeline_v1'
    if out.exists():
        raise RuntimeError('Pipeline already registered; inspect it instead of restarting')
    out.mkdir()
    files = list((ROOT / 'experiments/formal_evaluation').glob('*.py'))
    files += list((ROOT / 'experiments/deepseek_refinement').glob('*.py'))
    files += [ROOT / 'experiments/deepseek_pilot/rules.py', ROOT / 'docs/artifacts/operator_discovery_v1/repaired_library.json']
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (out / 'manifest.json').write_text(json.dumps({'sources': hashes, 'seeds': list(range(11,16)), 'extra_happo_audit_episodes': 200}, indent=2), encoding='utf-8')
    states = []

    def save(**extra):
        target = out / 'progress.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps({'runs': states, **extra}, indent=2), encoding='utf-8')
        temporary.replace(target)

    jobs = [(seed, 3, 'b', ['happo', 'llm_library']) for seed in range(12,16)]
    jobs += [(seed, 3, 'c', ['happo', 'llm_no_screen', 'llm_search_only', 'random_screen']) for seed in range(11,16)]
    jobs += [(seed, k, 'c', ['happo', 'llm_library']) for seed in range(11,16) for k in (1,5)]
    try:
        for seed, k, stage, methods in jobs:
            name = f'stage_{stage}_seed{seed}_k{k}_v1'
            training = ROOT / 'results/learning_curve' / (f'curve_seed{seed}_formal_v1' if seed != 11 else 'curve_seed11_until_stable_v1')
            while not (training / 'completion_audit.json').exists():
                save(status='waiting_training', seed=seed)
                driver = ROOT / 'results/formal_evaluation/multiseed_training_v1/completed.json'
                if driver.exists() and read(driver).get('status') == 'failed':
                    raise RuntimeError('Training driver failed; diagnose before evaluation')
                time.sleep(15)
            for rel, expected in hashes.items():
                if hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != expected:
                    raise RuntimeError(f'Source changed: {rel}')
            command = [sys.executable, '-u', str(ROOT / 'experiments/formal_evaluation/run.py'),
                       '--input-directory', str(ROOT / 'results/formal_evaluation/stage_a_inputs_v1'),
                       '--training-directory', str(training), '--methods', *methods,
                       '--stage', stage, '--report-interval', str(k), '--run-name', name]
            states.append({'name': name, 'status': 'running', 'command': command})
            save(status='running')
            with (out / f'{name}.log').open('w', encoding='utf-8') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                states[-1]['status'] = 'failed'
                raise RuntimeError(f'Suite failed: {name}; original outputs preserved')
            states[-1]['status'] = 'completed'
            save(status='running')
        save(status='evaluations_completed_analysis_pending')
        (out / 'completed.json').write_text(json.dumps({'status': 'evaluations_completed_analysis_pending', 'runs': states}, indent=2), encoding='utf-8')
    except Exception as exc:
        save(status='failed', error=repr(exc))
        raise


if __name__ == '__main__':
    main()
