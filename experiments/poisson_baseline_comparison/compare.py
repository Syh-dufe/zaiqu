"""Development-only stationary target selection and paired Poisson holdout."""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import itertools
import json
import math
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
OUT = ROOT / 'results/poisson_baseline_comparison/v1'
TRAIN = ROOT / 'results/poisson_optimality/formal_v1'
SPEC = ROOT / 'docs/superpowers/specs/2026-10-17-poisson-baseline-comparison-design.md'
PLAN = ROOT / 'docs/superpowers/plans/2026-10-17-poisson-baseline-comparison.md'
sys.path.insert(0, str(ROOT / 'experiments/poisson_optimality'))
import common as training_common
from environment import install
from train import parameter_sha
read, write, sha = training_common.read, training_common.write, training_common.sha

def trace_hash(path):
    return hashlib.sha256(json.dumps(list(map(int, path)), separators=(',', ':')).encode()).hexdigest()

def poisson_ppf(probability, mean):
    # All registered means are <=150; exp(-mean) is safely representable.
    assert 0 < probability < 1 and 0 < mean <= 150
    term = cumulative = math.exp(-mean)
    k = 0
    while cumulative < probability:
        k += 1
        term *= mean / k
        cumulative += term
        assert k < 10000
    return k

def grid(lead):
    candidates = {}
    bounds = []
    for allowance in (0, 1):
        ranges = []
        for i in range(1, 4):
            mean = 10 * i * (lead + allowance)
            low = max(0, poisson_ppf((4-i)/4, mean)-1)
            high = poisson_ppf((4-i)/(5-i), mean)
            ranges.append(range(low, high+1))
            bounds.append(dict(review_allowance=allowance, stage=i, mean=mean, low=low, high=high))
        for echelon in itertools.product(*ranges):
            if list(echelon) != sorted(echelon):
                continue
            target = (echelon[0], echelon[1]-echelon[0], echelon[2]-echelon[1])
            candidates.setdefault(target, []).append(allowance)
    return candidates, bounds

def scan_cost(paths, lead, target):
    """Vectorized across independent paths; never accesses future demand for action."""
    demand = np.asarray(paths, dtype=np.int64)
    n = len(paths)
    inv = np.zeros((n, 3), dtype=np.int64)
    back = inv.copy()
    unshipped = inv.copy()
    pipe = np.zeros((n, 3, lead), dtype=np.int64)
    costs = np.zeros(n, dtype=np.int64)
    for t in range(200):
        pos = inv + pipe.sum(axis=2) + unshipped - back
        q = np.clip(np.asarray(target)-pos, 0, 20)
        local = np.column_stack((demand[:, t], q[:, :2]))
        requested = local + back
        available = inv + pipe[:, :, 0]
        ships = np.minimum(requested, available)
        inv = available-ships
        back = requested-ships
        new_ships = np.column_stack((ships[:, 1:], q[:, 2]))
        unshipped += q-new_ships
        assert np.array_equal(unshipped[:, :2], back[:, 1:])
        assert np.all(unshipped >= 0) and np.all(unshipped[:, 2] == 0)
        pipe = np.concatenate((pipe[:, :, 1:], new_ships[:, :, None]), axis=2)
        costs += inv.sum(axis=1) + back[:, 0]
    return costs / 600

def load_policy(lead, seed):
    import torch
    from gym import spaces
    from algorithms.happo_policy import HAPPO_Policy
    folder = TRAIN / 'runs' / f'L{lead}_seed{seed}'
    cfg = read(folder / 'config.json')
    args = argparse.Namespace(**cfg['arguments'])
    policies = []
    for i in range(3):
        policy = HAPPO_Policy(args, spaces.Box(-np.inf, np.inf, shape=(lead+3,), dtype=np.float32),
                   spaces.Box(-np.inf, np.inf, shape=(3*(lead+3),), dtype=np.float32), spaces.Discrete(21),
                   device=torch.device('cpu'))
        for label in ('actor', 'critic'):
            getattr(policy, label).load_state_dict(torch.load(folder/'models'/f'{label}_agent{i}.pt',
                                                             map_location='cpu', weights_only=True))
            getattr(policy, label).eval()
        policies.append(policy)
    assert parameter_sha(policies) == read(folder / 'best.json')['parameter_sha256']
    return policies, args

def episode(env, path, lead, method, seed, index, split, writer=None, target=None, policies=None, args=None):
    import torch
    env.eval_data = [list(map(int, path))]
    env.n_eval = 1
    env.eval_index = 0
    obs = env.reset(train=False)
    unshipped = [0, 0, 0]
    states = [np.zeros((1, args.recurrent_N, args.hidden_size), dtype=np.float32) for _ in range(3)] if policies else None
    total = 0
    for t in range(200):
        old_inv, old_back = list(map(int, env.inventory)), list(map(int, env.backlog))
        pipeline = [list(map(int, p)) for p in env.order]
        positions = [old_inv[i]+sum(pipeline[i])+unshipped[i]-old_back[i] for i in range(3)]
        if policies:
            actions = []
            with torch.no_grad():
                for i, policy in enumerate(policies):
                    a, state = policy.act(np.asarray(obs[i])[None, :], states[i], np.ones((1, 1), dtype=np.float32), deterministic=True)
                    actions.append(int(a.item()))
                    states[i] = state.detach().cpu().numpy()
        else:
            actions = [max(0, min(20, int(target[i])-positions[i])) for i in range(3)]
        obs, reward, _, _ = env.step(actions, one_hot=False)
        assert all(0 <= q <= 20 for q in actions)
        newly_shipped = [int(env.order[i][-1]) for i in range(3)]
        for i in range(3):
            old_outstanding = unshipped[i]
            unshipped[i] += actions[i]-newly_shipped[i]
            assert unshipped[i] == (int(env.backlog[i+1]) if i < 2 else 0)
            cost = int(env.inventory[i]) + (int(env.backlog[i]) if i == 0 else 0)
            assert cost == -reward[i][0]
            total += cost
            if writer:
                writer.writerow(dict(split=split, method=method, lead=lead, seed=seed, path=index, t=t, node=i,
                   demand=int(path[t]), old_inventory=old_inv[i], old_backlog=old_back[i],
                   old_pipeline=json.dumps(pipeline[i], separators=(',', ':')), outstanding_before=old_outstanding,
                   position=positions[i], target='' if target is None else target[i], action=actions[i],
                   shipment=newly_shipped[i], outstanding_after=unshipped[i], inventory=int(env.inventory[i]),
                   backlog=int(env.backlog[i]), pipeline=json.dumps(list(map(int, env.order[i])), separators=(',', ':')),
                   cost=cost))
    return dict(split=split, method=method, lead=lead, seed=seed, path=index,
                demand_sha256=trace_hash(path), cost=total/600)

def verify():
    training_common.verify()
    r = read(OUT / 'registration.json')
    for entry in r['files']:
        assert sha(ROOT / entry['path']) == entry['sha256'], entry['path']
    return r

def archive(destination, files):
    import winreg
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as reg:
            key = winreg.QueryValueEx(reg, 'DEEPSEEK_API_KEY')[0].encode()
    except OSError:
        key = b''
    entries = []
    for i, p in enumerate(sorted(set(files))):
        raw = p.read_bytes()
        assert not key or key not in raw
        gz = destination / f'{i:04d}.gz'
        gz.write_bytes(gzip.compress(raw, mtime=0))
        assert gzip.decompress(gz.read_bytes()) == raw
        entries.append(dict(source=p.relative_to(ROOT).as_posix(), archive=gz.name,
                            sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)))
    write(destination / 'manifest.json', dict(files=entries, user_key_absent=True, lossless=True))

def prepare():
    assert not OUT.exists()
    assert read(TRAIN / 'completed.json')['jobs'] == 10
    training_common.verify()
    OUT.mkdir(parents=True)
    files = [ROOT / e['path'] for e in read(TRAIN / 'freeze.json')['files']]
    files += [*HERE.glob('*.py'), SPEC, PLAN, TRAIN/'completed.json', TRAIN/'summary.json']
    files += list((OUT.parent/'preparation_diagnostics').glob('*'))
    for folder in sorted((TRAIN/'runs').iterdir()):
        for name in ('config.json', 'completed.json', 'best.json', 'training_demands.jsonl'):
            files.append(folder / name)
        files += list((folder/'models').glob('*.pt'))
    write(OUT / 'registration.json', dict(files=[dict(path=p.relative_to(ROOT).as_posix(), sha256=sha(p)) for p in sorted(set(files))],
          api_calls=0, frozen_before_development=True, model_seeds=list(range(11, 16)), lead_times=[2, 4],
          holdout_episodes=240, validation_episodes=200, holdout_node_periods=144000))
    print('PREPARED', flush=True)

def preflight():
    import torch
    torch.set_num_threads(1)
    verify()
    data = read(TRAIN/'inputs.json')['baseline_development'][:1]
    evidence = []
    for lead in (2, 4):
        wrappers, stream = install(lead, OUT/f'preflight_demands_L{lead}.jsonl')
        env = wrappers.Env()
        candidates, bounds = grid(lead)
        target = sorted(candidates)[len(candidates)//2]
        a = scan_cost(data, lead, target)[0]
        b = episode(env, data[0], lead, 'base_stock', -1, 0, 'fixture', target=target)['cost']
        assert abs(a-b) < 1e-12
        policies, args = load_policy(lead, 11)
        episode(env, data[0], lead, 'happo', 11, 0, 'fixture', policies=policies, args=args)
        assert parameter_sha(policies) == read(TRAIN/'runs'/f'L{lead}_seed11'/'best.json')['parameter_sha256']
        evidence.append(dict(lead=lead, candidates=len(candidates), vector_scalar_cost_equal=True,
                             checked_steps=env.checked_steps, actor_dim=lead+3, critic_dim=3*(lead+3), bounds=bounds))
        stream.close()
    verify()
    write(OUT/'preflight.json', dict(passed=True, fixture_episodes=4, api_calls=0, evidence=evidence))
    archive(ROOT/'docs/artifacts/poisson_baseline_comparison_preregistration',
            [ROOT/e['path'] for e in read(OUT/'registration.json')['files']]+list(OUT.glob('*.json')))
    print('PREFLIGHT PASSED', flush=True)

def run():
    import torch
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    verify()
    assert read(OUT/'publication.json')['verified']
    assert read(OUT/'preflight.json')['passed']
    with (OUT/'started.lock').open('x') as f: f.write(str(os.getpid()))
    write(OUT/'launch.json', dict(pid=os.getpid(), timestamp=time.time()))
    start = time.time()
    results, selected = [], {}
    try:
        development = read(TRAIN/'inputs.json')['baseline_development']
        for lead in (2, 4):
            records = []
            candidates, bounds = grid(lead)
            for index, (target, origins) in enumerate(sorted(candidates.items())):
                costs = scan_cost(development, lead, target)
                records.append(dict(target=list(target), origins=origins, cost=float(costs.mean()), path_costs=costs.tolist()))
                if index % 20 == 0:
                    write(OUT/'progress.json', dict(status='running', stage='baseline_development', lead=lead,
                                                  candidates_completed=index+1, total=len(candidates), api_calls=0))
            choice = min(records, key=lambda r:(r['cost'], r['target']))
            selected[str(lead)] = dict(selected=choice, paper_grid_best=min((r for r in records if 0 in r['origins']), key=lambda r:(r['cost'],r['target'])), bounds=bounds)
            write(OUT/f'development_L{lead}.json', records)
        write(OUT/'selection.json', selected)
        selection_sha = sha(OUT/'selection.json')
        seen = set()
        original = read(TRAIN/'inputs.json')
        for name in ('validation','baseline_development'):
            seen.update(trace_hash(p) for p in original[name])
        for p in (TRAIN/'runs').glob('*/training_demands.jsonl'):
            with p.open(encoding='utf-8') as f:
                for line in f: seen.add(trace_hash(json.loads(line)))
        historical_count = len(seen)
        rng = np.random.default_rng(20275003)
        paths, rejected = [], 0
        while len(paths) < 20:
            path = rng.poisson(10, 200).tolist()
            h = trace_hash(path)
            if h in seen:
                rejected += 1
                continue
            seen.add(h)
            paths.append(path)
        write(OUT/'holdout_inputs.json', dict(paths=paths, seed=20275003, selection_sha256=selection_sha,
              historical_unique_traces=historical_count, rejected_collisions=rejected, generated_after_selection=True))
        fields = 'split method lead seed path t node demand old_inventory old_backlog old_pipeline outstanding_before position target action shipment outstanding_after inventory backlog pipeline cost'.split()
        for lead in (2, 4):
            wrappers, stream = install(lead, OUT/f'evaluation_demands_L{lead}.jsonl')
            env = wrappers.Env()
            target = selected[str(lead)]['selected']['target']
            with gzip.open(OUT/f'periods_L{lead}.csv.gz','wt',encoding='utf-8',newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                for seed in range(11,16):
                    verify()
                    policies, args = load_policy(lead, seed)
                    valid = []
                    for index, path in enumerate(original['validation']):
                        row = episode(env,path,lead,'happo',seed,index,'validation',writer,policies=policies,args=args)
                        results.append(row)
                        valid.append(row['cost'])
                    expected = read(TRAIN/'runs'/f'L{lead}_seed{seed}'/'best.json')['validation_cost']
                    assert np.isclose(np.mean(valid), expected, rtol=0, atol=1e-9)
                    for index, path in enumerate(paths):
                        results.append(episode(env,path,lead,'happo',seed,index,'holdout',writer,policies=policies,args=args))
                    assert parameter_sha(policies) == read(TRAIN/'runs'/f'L{lead}_seed{seed}'/'best.json')['parameter_sha256']
                    write(OUT/'episodes.json', results)
                    write(OUT/'progress.json', dict(status='running',stage='evaluation',lead=lead,seed=seed,completed_episodes=len(results),api_calls=0))
                for index, path in enumerate(paths):
                    results.append(episode(env,path,lead,'base_stock',-1,index,'holdout',writer,target=target))
            stream.close()
        assert sha(OUT/'selection.json') == selection_sha
        assert len(results) == 440
        write(OUT/'episodes.json', results)
        verify()
        write(OUT/'simulation_completed.json', dict(episodes=440, validation_episodes=200, holdout_episodes=240,
              node_periods=264000, api_calls=0, seconds=time.time()-start, selection_sha256=selection_sha))
        subprocess.run([sys.executable,str(HERE/'audit.py')],cwd=ROOT,check=True)
        write(OUT/'completed.json', read(OUT/'simulation_completed.json'))
        write(OUT/'progress.json', dict(status='completed',episodes=440,api_calls=0))
        archive(ROOT/'docs/artifacts/poisson_baseline_comparison_completed', [p for p in OUT.rglob('*') if p.is_file()]+list(HERE.glob('*.py'))+[SPEC,PLAN])
        print('COMPLETED',flush=True)
    except BaseException:
        write(OUT/'failed.json', dict(traceback=traceback.format_exc(),episodes=len(results),api_calls=0))
        write(OUT/'progress.json', dict(status='failed',episodes=len(results),api_calls=0))
        raise

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['prepare','preflight','run'])
    globals()[p.parse_args().action]()
