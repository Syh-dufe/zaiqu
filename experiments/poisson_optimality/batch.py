"""Register, check and uniquely dispatch ten serial Poisson training tasks."""
import argparse
import gzip
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from common import AUTHOR, OUT, ROOT, read, sha, sources, verify, write

def prepare():
    assert not OUT.exists(), 'preserve previous outputs'
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=AUTHOR, text=True).strip() == 'a7e5a3e83e21565a5799483bc534e39635ec65dd'
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=AUTHOR, text=True).strip()
    OUT.mkdir(parents=True)
    # Freeze method before first generation of these inputs.
    entries = [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for p in sources()]
    write(OUT / 'method_freeze.json', {'files': entries, 'timestamp': time.time()})
    import numpy as np
    inputs = {}
    seen = set()
    for name, seed in [('validation', 20275001), ('baseline_development', 20275002)]:
        rng = np.random.default_rng(seed)
        paths = []
        while len(paths) < 20:
            path = rng.poisson(10, 200).tolist()
            if tuple(path) in seen:
                continue
            seen.add(tuple(path))
            paths.append(path)
        inputs[name] = paths
    write(OUT / 'inputs.json', {'generator': 'numpy.default_rng.poisson(10,200)',
          'seeds': [20275001, 20275002], 'historical_role': 'new stationary validation/development; not disaster test',
          'unique_sequences': len(seen), **inputs})
    entries.extend({'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
                   for p in [OUT / 'inputs.json', OUT / 'method_freeze.json'])
    write(OUT / 'freeze.json', {'files': entries, 'jobs': [{'lead': l, 'seed': s} for l in (2, 4) for s in range(11, 16)],
          'max_steps': 30000000, 'api_calls': 0, 'max_parallel': 1})
    print('PREPARED', len(entries), flush=True)

def preflight():
    verify()
    for lead in (2, 4):
        with (OUT / f'fixture_L{lead}.log').open('x', encoding='utf-8') as log:
            subprocess.run([sys.executable, str(Path(__file__).with_name('train.py')), '--lead', str(lead),
                            '--seed', '11', '--budget', '1000', '--fixture'],
                           cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        result = read(OUT / 'fixtures' / f'L{lead}_seed11' / 'completed.json')
        assert result['completed_steps'] == 1000 and result['agent_updates'] == [1, 1, 1]
        assert result['audited_training_steps'] == 1000
    write(OUT / 'preflight.json', {'passed': True, 'lead_times': [2, 4], 'fixture_training_steps': 2000,
                                 'api_calls': 0, 'formal_results': False})
    print('PREFLIGHT PASSED', flush=True)

def register():
    verify()
    assert read(OUT / 'preflight.json')['passed']
    destination = ROOT / 'docs/artifacts/poisson_optimality_preregistration'
    destination.mkdir(parents=True, exist_ok=False)
    paths = [ROOT / e['path'] for e in read(OUT / 'freeze.json')['files']]
    paths.extend(p for p in OUT.rglob('*') if p.is_file())
    paths = sorted(set(paths))
    # Read only the named User credential, never serialize it.
    key = subprocess.check_output(['powershell', '-NoProfile', '-Command',
          "[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')"], text=True).strip()
    encoded_key = key.encode() if key else None
    manifest = []
    for i, path in enumerate(paths):
        raw = path.read_bytes()
        assert not encoded_key or encoded_key not in raw, 'credential found'
        gz = destination / f'{i:04d}.gz'
        gz.write_bytes(gzip.compress(raw, mtime=0))
        assert gzip.decompress(gz.read_bytes()) == raw
        manifest.append({'source': path.relative_to(ROOT).as_posix(), 'archive': gz.name,
                         'sha256': sha(path), 'bytes': len(raw)})
    write(destination / 'manifest.json', {'files': manifest, 'user_key_absent': True,
          'fixture_weights_only': True, 'formal_training_not_started': True})
    write(OUT / 'registration.json', {'manifest': str(destination / 'manifest.json'),
                                    'sha256': sha(destination / 'manifest.json'), 'api_calls': 0})
    print('REGISTERED', len(manifest), flush=True)

def run():
    verify()
    assert read(OUT / 'publication.json')['verified']
    assert read(OUT / 'preflight.json')['passed']
    with (OUT / 'started.lock').open('x') as f:
        f.write(str(os.getpid()))
    write(OUT / 'launch.json', {'pid': os.getpid(), 'executable': sys.executable, 'started': time.time()})
    completed = []
    try:
        for job in read(OUT / 'freeze.json')['jobs']:
            verify()
            label = f"L{job['lead']}_seed{job['seed']}"
            write(OUT / 'progress.json', {'status': 'running', 'completed': completed, 'current': label,
                                        'total_jobs': 10, 'api_calls': 0})
            with (OUT / f'{label}.log').open('x', encoding='utf-8') as log:
                child = subprocess.Popen([sys.executable, '-u', str(Path(__file__).with_name('train.py')),
                         '--lead', str(job['lead']), '--seed', str(job['seed'])], cwd=ROOT,
                         stdout=log, stderr=subprocess.STDOUT)
                write(OUT / 'active.json', {'job': label, 'pid': child.pid, 'started': time.time()})
                assert child.wait() == 0, f'{label} failed; preserve log'
            verify()
            result = read(OUT / 'runs' / label / 'completed.json')
            assert result['best'] is not None and result['api_calls'] == 0
            completed.append(label)
        summaries = [read(OUT / 'runs' / label / 'completed.json') for label in completed]
        write(OUT / 'summary.json', {'jobs': summaries, 'api_calls': 0})
        write(OUT / 'completed.json', {'jobs': len(completed), 'timestamp': time.time(),
              'total_steps': sum(r['completed_steps'] for r in summaries), 'api_calls': 0,
              'comparison_pending': True})
        write(OUT / 'progress.json', {'status': 'completed', 'completed': completed, 'total_jobs': 10})
    except BaseException:
        write(OUT / 'failed.json', {'completed': completed, 'traceback': traceback.format_exc()})
        write(OUT / 'progress.json', {'status': 'failed', 'completed': completed, 'total_jobs': 10})
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'preflight', 'register', 'run'])
    globals()[parser.parse_args().mode]()
