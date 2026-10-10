"""Register immutable mixed-demand training and dispatch exactly one serial batch."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from demand import ROOT,OUT,TYPES,sample,digest_trace

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

extension=load('normal_extension_util',ROOT/'experiments/happo_seed_extension/batch.py')
read,write,sha=extension.read,extension.write,extension.sha
SEEDS=list(range(11,16))
AUTHOR=ROOT/'external/liu-inventory'
PLAN=ROOT/'docs/superpowers/plans/2026-10-10-mixed-shock-happo.md'
SPEC=ROOT/'docs/superpowers/specs/2026-10-10-mixed-shock-happo-design.md'

def name(seed):return f'mixed_shock_seed{seed}_v1'
def directory(seed):return ROOT/'results/learning_curve'/name(seed)
def command(seed,action='train'):
    return [sys.executable,'-u',str(Path(__file__).with_name('entry.py')),action,'--seed',str(seed)]

def verify(manifest):extension.verify(manifest)

def register():
    assert not OUT.exists()
    for seed in SEEDS:
        assert not directory(seed).exists()
        assert not (ROOT/'external/results/MyEnv/Emergency_Replenishment_Compatibility/happo'/name(seed)).exists()
    sys.path.insert(0,str(AUTHOR))
    # Reuse the registered history extractor; neither simulations nor API run.
    history=load('mixed_history_inventory',ROOT/'experiments/joint_baseline_confirmation/batch.py')
    used,sources=history.historical_traces(OUT)
    used_hashes={digest_trace(trace) for trace in used}
    original_state=np.random.get_state();np.random.seed(20272011)
    records=[];seen=set(used_hashes);rejections=0
    try:
        for kind in TYPES:
            for index in range(20):
                for attempt in range(10000):
                    row=sample(kind)
                    pair_hashes={digest_trace(row['base']),digest_trace(row['demand'])}
                    if not (pair_hashes & seen):break
                    rejections+=1
                else:raise RuntimeError('Validation generation exhaustion')
                seen.update(pair_hashes);records.append(dict(index=index,**row))
    finally:np.random.set_state(original_state)
    from config import get_config
    launcher=load('mixed_config_launcher',ROOT/'experiments/emergency_compatibility/train.py')
    configs={}
    for seed in SEEDS:
        new=vars(launcher.seed_list_parser(get_config).parse_args(['--scenario_name',launcher.SCENARIO,'--experiment_name',name(seed),'--seed',str(seed),'--num_env_steps','3000000','--n_no_improvement_thres','40']))
        old=read(ROOT/f'docs/artifacts/formal_bc_v1/training/{seed}/config.json')['config']
        assert set(new)==set(old)
        assert {k for k in new if new[k]!=old[k]} <= {'experiment_name'}
        assert new['n_rollout_threads']==5 and new['episode_length']==200
        configs[str(seed)]=new
    files=list(AUTHOR.rglob('*.py'))+list((AUTHOR/'test_data/test_demand_merton').glob('*.txt'))
    files+=list(Path(__file__).parent.glob('*.py'))+[PLAN,SPEC,ROOT/'experiments/happo_seed_extension/batch.py',ROOT/'experiments/learning_curve/run.py',ROOT/'experiments/emergency_compatibility/train.py',ROOT/'experiments/formal_evaluation/audit_training.py',ROOT/'scripts/plot_learning_curve.py',ROOT/'experiments/joint_baseline_confirmation/batch.py']
    models={}
    for seed in range(11,21):
        target=ROOT/'results/learning_curve'/('curve_seed11_until_stable_v1' if seed==11 else f'curve_seed{seed}_formal_v1' if seed<=15 else f'curve_seed{seed}_extension_v1')
        done=read(target/'completed.json');model_dir=Path(done['final_model_directory']).parent/'models'
        files.extend([target/'config.json',target/'completed.json'])
        for p in model_dir.glob('*.pt'):models[str(p)]=sha(p)
    assert len(models)==60
    for p in files:
        if p.suffix=='.py':compile(p.read_bytes(),str(p),'exec')
    manifest=dict(seeds=SEEDS,parallel_limit=1,budget_per_seed=3000000,api_calls=0,
        author_commit='a7e5a3e83e21565a5799483bc534e39635ec65dd',old_models=models,
        hashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(set(files))},
        validation_count=100,model_selection='Original scheduled best on balanced mixed validation',
        commands={str(seed):command(seed) for seed in SEEDS},python=sys.version,executable=sys.executable)
    verify(manifest)
    OUT.mkdir(parents=True)
    write(OUT/'validation.json',dict(seed=20272011,records=records))
    write(OUT/'collision_inventory.json',dict(historical_unique_paths=len(used),sources=sources,rejected=rejections,selection='Exact collisions only, no policy costs'))
    for p in (OUT/'validation.json',OUT/'collision_inventory.json'):manifest['hashes'][str(p.relative_to(ROOT)).replace('\\','/')]=sha(p)
    write(OUT/'manifest.json',manifest)
    write(OUT/'preflight.json',dict(passed=True,configs=configs,old_model_count=len(models),validation_count=100,validation_unique=len({digest_trace(r['demand']) for r in records}),training_steps=0,api_calls=0))
    verify(manifest)
    print('MIXED_REGISTERED',len(files),len(records),len(used),flush=True)

def run():
    manifest=read(OUT/'manifest.json');verify(manifest)
    assert read(OUT/'preflight.json')['passed']
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0]
    assert revision==remote
    with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
    start=time.time();states={str(seed):dict(status='queued') for seed in SEEDS}
    write(OUT/'launch.json',dict(pid=os.getpid(),started=start,revision=revision))
    def update(seed,**values):
        states[str(seed)].update(values);write(OUT/'progress.json',dict(seeds=states,started=start,parallel_limit=1))
    try:
        for seed in SEEDS:
            verify(manifest)
            with (OUT/f'seed{seed}_train.log').open('x',encoding='utf-8') as log:
                child=subprocess.Popen(command(seed),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                update(seed,status='training',pid=child.pid)
                assert child.wait()==0,f'Training failed seed{seed}'
            verify(manifest);update(seed,status='auditing')
            with (OUT/f'seed{seed}_audit.log').open('x',encoding='utf-8') as log:
                subprocess.run(command(seed,'audit'),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
                subprocess.run([sys.executable,str(ROOT/'scripts/plot_learning_curve.py'),str(directory(seed))],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
            done=read(directory(seed)/'completed.json');verify(manifest)
            update(seed,status='completed',steps=done['completed_steps'],stop_reason=done['stop_reason'],stable=done['stability']['stable'],best_mixed_validation_cost=done['official_best_cost'])
        write(OUT/'completed.json',dict(seeds=states,wall_seconds=time.time()-start,api_calls=0))
    except Exception as exc:
        write(OUT/'failed.json',dict(error=str(exc),seeds=states,preserved=True));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['register','verify','run'])
    action=parser.parse_args().action
    if action=='register':register()
    elif action=='run':run()
    else:verify(read(OUT/'manifest.json'))
