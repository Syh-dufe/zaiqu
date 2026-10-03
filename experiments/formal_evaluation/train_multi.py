"""Run exactly four normal-demand training seeds, two concurrently."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[2]


def main():
    out=ROOT/'results/formal_evaluation/multiseed_training_v1'
    if out.exists():raise RuntimeError('Driver already registered: check progress/processes; do not duplicate')
    for seed in range(12,16):
        if (ROOT/f'results/learning_curve/curve_seed{seed}_formal_v1').exists():raise RuntimeError('Seed output already exists')
    out.mkdir();(out/'sources').mkdir()
    files=[ROOT/'experiments/learning_curve/run.py',ROOT/'experiments/emergency_compatibility/train.py',Path(__file__),Path(__file__).with_name('audit_training.py')]
    manifest=dict(seeds=[12,13,14,15],parallel_limit=2,budget_per_seed=3000000,patience=40,until_stable=True,
        training='Original normal Merton demand only; original 20 validation demand traces',
        project_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    for p in files:shutil.copy2(p,out/'sources'/('_'.join(p.relative_to(ROOT).parts)))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    states={str(seed):dict(status='queued') for seed in range(12,16)};lock=threading.Lock();failed=threading.Event();started=time.time()
    def update(seed,**record):
        with lock:
            states[str(seed)].update(record)
            (out/'progress.json').write_text(json.dumps(dict(seeds=states,started_at_unix=started),indent=2),encoding='utf-8')
    def train(seed):
        if failed.is_set():update(seed,status='not_started_after_failure');return
        name=f'curve_seed{seed}_formal_v1';directory=ROOT/'results/learning_curve'/name
        command=[sys.executable,'-u',str(ROOT/'experiments/learning_curve/run.py'),'--seed',str(seed),'--budget','3000000','--patience','40','--until-stable','--run-name',name]
        logfile=ROOT/'results/learning_curve'/(name+'_train.log')
        update(seed,status='starting',command=command,log=str(logfile))
        with logfile.open('w',encoding='utf-8') as log:
            process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            update(seed,status='training',pid=process.pid)
            code=process.wait()
        if code:
            failed.set();update(seed,status='failed',exit_code=code);raise RuntimeError(f'Training failed seed {seed}; preserve results')
        if any(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha for name,sha in manifest['source_sha256'].items()):
            failed.set();update(seed,status='source_changed');raise RuntimeError('Training/audit sources changed while running')
        update(seed,status='auditing')
        with (out/f'seed{seed}_audit.log').open('w',encoding='utf-8') as log:
            code=subprocess.call([sys.executable,'-u',str(Path(__file__).with_name('audit_training.py')),str(directory)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            if not code:code=subprocess.call([sys.executable,str(ROOT/'scripts/plot_learning_curve.py'),str(directory)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if code:
            failed.set();update(seed,status='audit_failed',exit_code=code);raise RuntimeError(f'Audit failed seed {seed}')
        done=json.loads((directory/'completed.json').read_text(encoding='utf-8-sig'))
        update(seed,status='completed',steps=done['completed_steps'],stop_reason=done['stop_reason'],stable=done['stability']['stable'])
        print('SEED_COMPLETED',seed,done['completed_steps'],done['stop_reason'],flush=True)
    errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(train,seed):seed for seed in range(12,16)}
        for future in concurrent.futures.as_completed(futures):
            try:future.result()
            except Exception as exc:errors.append(dict(seed=futures[future],error=str(exc)))
    (out/'completed.json').write_text(json.dumps(dict(status='failed' if errors else 'completed',errors=errors,seeds=states,wall_seconds=time.time()-started),indent=2),encoding='utf-8')
    if errors:raise RuntimeError('Training queue had failures; check recorded logs')
    print('FOUR_SEEDS_COMPLETED',flush=True)


if __name__=='__main__':main()
