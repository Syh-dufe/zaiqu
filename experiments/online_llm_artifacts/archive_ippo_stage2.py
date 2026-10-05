"""Audit and preserve full IPPO training locally; publish logs and selected weights."""
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT/'results/ippo_baseline_stage2/formal_v1'
LOCAL = ROOT/'results/ippo_baseline_stage2_archive/formal_v1'
PUBLIC = ROOT/'docs/artifacts/ippo_baseline_stage2_completed'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not LOCAL.exists() and not PUBLIC.exists(), 'Preserve existing archive'
    manifest = read(DRIVER/'manifest.json')
    driver = read(DRIVER/'completed.json')
    assert driver['status'] == 'completed' and not driver['errors']
    for path, digest in manifest['hashes'].items():
        assert sha(ROOT/path) == digest, path
    for path, digest in manifest['frozen_happo_models'].items():
        assert sha(Path(path)) == digest, path
    import torch
    torch.set_num_threads(1)

    def parameters(directory):
        digest = hashlib.sha256()
        for agent in range(3):
            for label in ('actor', 'critic'):
                state = torch.load(directory/f'{label}_agent{agent}.pt', weights_only=True, map_location='cpu')
                for name, value in state.items():
                    digest.update(name.encode()); digest.update(value.numpy().tobytes())
        return digest.hexdigest()

    results = []
    paths = list(DRIVER.rglob('*')) + [ROOT/p for p in manifest['hashes']]
    for seed in range(11, 16):
        target = ROOT/f'results/ippo_learning_curve/ippo_seed{seed}_formal_v1'
        done = read(target/'completed.json')
        audit = read(target/'completion_audit.json')
        factors = read(target/'ippo_update_audit.json')
        assert len(factors) == 3 * done['completed_steps']//1000
        assert all(f['factor_min'] == f['factor_max'] == 1 and f['critic_dim'] == f['local_dim'] == 7 for f in factors)
        assert all(sorted(f['agent'] for f in factors[i:i+3]) == [0,1,2] for i in range(0,len(factors),3))
        rows = list(csv.DictReader((target/'curve.csv').open()))
        evaluations = [r for r in rows if r['phase']=='evaluation' and int(r['step'])>0]
        assert len([r for r in rows if r['phase']=='training']) == done['completed_steps']//1000
        costs = [float(r['mean_actor_period_cost']) for r in evaluations[:-1]]
        previous, recent = costs[-20:-10], costs[-10:]
        stable = (done['completed_steps']>=100000 and len(costs)>=20
                  and abs(statistics.median(recent)-statistics.median(previous))/max(abs(statistics.median(previous)),1e-8)<=.01
                  and abs(min(recent)-min(previous))/max(abs(min(previous)),1e-8)<=.01
                  and statistics.pstdev(recent)/max(abs(statistics.mean(recent)),1e-8)<=.05)
        assert stable == done['stability']['stable']
        eligible = evaluations[:-1]
        if done['stop_reason']=='empirical_plateau':
            eligible = eligible[:-1]
        best = min(eligible,key=lambda r:float(r['mean_actor_period_cost']))
        assert int(best['step']) == done['best_scheduled_evaluation']['step']
        assert float(best['mean_actor_period_cost']) == done['official_best_cost']
        final = Path(done['final_model_directory'])
        snapshots = read(target/'snapshots.json')
        selected = next(x for x in snapshots if x['step']==int(best['step']))
        assert parameters(final.parent/'models') == selected['parameter_sha256']
        assert parameters(final) == snapshots[-1]['parameter_sha256']
        assert audit['evaluated_original_costs']['official_best'] == done['official_best_cost']
        assert audit['evaluated_original_costs']['final'] == done['final_eval_cost']
        assert done['max_reload_error']==0 and done['eval_traces']==20
        original = read(ROOT/f'docs/artifacts/formal_bc_v1/training/{seed}/completed.json')
        results.append(dict(seed=seed, steps=done['completed_steps'], stop_reason=done['stop_reason'],
                            stable=stable, best_cost=done['official_best_cost'], final_cost=done['final_eval_cost'],
                            best_step=int(best['step']), happo_normal_validation_best=original['official_best_cost']))
        paths += list(target.rglob('*')) + list(final.parent.rglob('*'))
    assert not subprocess.check_output(['git','-C',str(ROOT/'external/liu-inventory'),'diff','HEAD','--name-only']).strip()
    LOCAL.mkdir(parents=True); PUBLIC.mkdir(parents=True)
    hashes = {}; published = {}; snapshots = {}
    key = os.environ.get('DEEPSEEK_API_KEY','')
    assert key, 'Supply User key for absence scan; no API calls'
    for path in sorted(set(paths)):
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        rel = path.relative_to(ROOT)
        data = path.read_bytes()
        assert key.encode() not in data, str(rel)
        dest = LOCAL/rel; dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        assert sha(dest)==digest
        hashes[rel.as_posix()] = digest
        if 'curve_snapshots' in rel.parts and path.suffix=='.pt':
            snapshots[rel.as_posix()]=digest
        else:
            public = PUBLIC/rel; public.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(dest,public); assert sha(public)==digest
            published[rel.as_posix()] = digest
    summary = dict(status='completed', independent_audit_passed=True, seeds=results,
                   total_steps=sum(x['steps'] for x in results), wall_seconds=driver['wall_seconds'], api_calls=0,
                   mean_best_cost=statistics.mean(x['best_cost'] for x in results),
                   mean_final_cost=statistics.mean(x['final_cost'] for x in results),
                   mean_happo_normal_validation_best=statistics.mean(x['happo_normal_validation_best'] for x in results),
                   local_full_archive=str(LOCAL), local_file_count=len(hashes),
                   public_file_count=len(published), locally_preserved_snapshot_weight_files=len(snapshots),
                   scope='Normal validation/model selection only, not unseen disaster comparison')
    for folder, name, value in ((LOCAL,'export_hashes.json',hashes),(PUBLIC,'export_hashes.json',published),
                                (PUBLIC,'locally_preserved_snapshot_hashes.json',snapshots),
                                (PUBLIC,'summary.json',summary),(LOCAL,'summary.json',summary)):
        (folder/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
