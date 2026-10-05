"""Registered, no-API development scan on exposed v5b batches 01/06."""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
import numpy as np
from policy import BaseStock

ROOT = Path(__file__).resolve().parents[2]
AUTHOR = ROOT/'external/liu-inventory'
OUT = ROOT/'results/base_stock_baseline/development_v1'
OLD = ROOT/'results/online_llm_shock_types/confirmation_v5b'
sys.path.insert(0, str(AUTHOR))
from envs.serial import Env


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def episode(demand, z=8, information='local', rounding='ceil', initial_history=None):
    previous = Path.cwd()
    try:
        os.chdir(AUTHOR)
        env = Env()
    finally:
        os.chdir(previous)
    env.eval_data = [list(demand)]
    env.n_eval = 1
    env.reset(train=False, normalize=False)
    policy = BaseStock(z, information, rounding, initial_history)
    rows = []
    for period in range(200):
        decisions = policy.decide(env.inventory, env.backlog, env.order)
        orders = [d['action'] for d in decisions]
        before = [(float(env.inventory[i]), float(env.backlog[i]), [float(x) for x in env.order[i]]) for i in range(3)]
        _, rewards, _, _ = env.step(orders, one_hot=False)
        shipped = [float(env.order[i][-1]) for i in range(3)]
        local = [demand[period]]+orders[:-1]
        policy.observe(local, orders, shipped)
        # Audit only: neighboring backlog is never supplied to the policy.
        for i in range(3):
            expected_pending = float(env.backlog[i+1]) if i < 2 else 0.0
            if abs(policy.unshipped[i]-expected_pending)>1e-8:
                raise AssertionError('Local outstanding ledger differs from supplier backlog')
            if abs(float(rewards[i][0])+float(env.inventory[i]+env.backlog[i]))>1e-8:
                raise AssertionError('Reward differs from original I+B cost')
            rows.append(dict(period=period, node=i, before_inventory=before[i][0],
                             before_backlog=before[i][1], before_pipeline=json.dumps(before[i][2]),
                             **decisions[i], demand=float(local[i]), newly_shipped=shipped[i],
                             after_unshipped=policy.unshipped[i], inventory=float(env.inventory[i]),
                             backlog=float(env.backlog[i]), cost=float(env.inventory[i]+env.backlog[i])))
    return dict(cost=float(np.mean([r['cost'] for r in rows])),
                downstream_backlog=float(np.mean([r['backlog'] for r in rows if r['node']==0])),
                ledger_verified=True, rows=rows)


def register():
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT/'inputs').mkdir()
    sources = list((ROOT/'experiments/base_stock_baseline').glob('*.py'))
    sources += [AUTHOR/'envs/serial.py', AUTHOR/'envs/generator.py',
                ROOT/'docs/superpowers/plans/2026-10-05-nonstationary-base-stock-baseline.md',
                ROOT/'docs/2026-10-05-base-stock-development-protocol.md']
    frozen = {str(p.relative_to(ROOT)):sha(p) for p in sources}
    inputs = []
    for batch in (1, 6):
        source = OLD/f'inputs/batch{batch:02}.json'
        target = OUT/f'inputs/batch{batch:02}.json'
        target.write_bytes(source.read_bytes())
        inputs.append(dict(batch=batch, path=str(target), sha256=sha(target), source=str(source)))
        frozen[str(source.relative_to(ROOT))] = sha(source)
    # Independent normal-validation history is already exposed; never future test data.
    normal = sorted((AUTHOR/'test_data/test_demand_merton').glob('*'))[0]
    history = [int(x) for x in normal.read_text().split()][-40:]
    save(OUT/'inputs/normal_initial_history.json', dict(source=str(normal), sha256=sha(normal), values=history))
    frozen[str(normal.relative_to(ROOT))] = sha(normal)
    for seed in range(11,16):
        for batch in (1,6):
            p = OLD/f'runs/seed{seed}_batch{batch:02}/episodes.json'
            frozen[str(p.relative_to(ROOT))] = sha(p)
    save(OUT/'freeze.json', frozen)
    save(OUT/'manifest.json', dict(development_only=True, api_calls=0, model_training=False,
          input_batches=inputs, candidate_z=list(range(20)), H=40, L=4,
          main_information='local', approximation_information='report_mean',
          selection='minimum mean shock cost, equal four-type weights; ties smaller z',
          sensitivity='at z8 and selected local z: floor, exposed normal initial history',
          initial_history=[10]*40, reference_z=8, expected_scan_episodes=640,
          expected_sensitivity_episodes=64, expected_node_periods=422400,
          caveat='Already exposed development inputs; no independent generalization claim'))


def check_freeze():
    for path, expected in json.loads((OUT/'freeze.json').read_text()).items():
        if sha(ROOT/path)!=expected:
            raise AssertionError(f'Frozen object changed: {path}')
    for item in json.loads((OUT/'manifest.json').read_text())['input_batches']:
        if sha(item['path'])!=item['sha256']:
            raise AssertionError('Registered input changed')


def evaluate(config, scores):
    check_freeze()
    folder = OUT/'runs'/config['name']
    folder.mkdir(parents=True, exist_ok=False)
    path = folder/'periods.csv.gz'
    with gzip.open(path, 'wt', encoding='utf-8', newline='') as handle:
        writer = None
        for batch in (1,6):
            inputs = json.loads((OUT/f'inputs/batch{batch:02}.json').read_text())
            for trace, event in enumerate(inputs['events']):
                for scenario in ('base','shock'):
                    result = episode(inputs[scenario][trace], **{k:v for k,v in config.items() if k!='name'})
                    identity = dict(config=config['name'], batch=batch, trace=trace, type=event['type'], scenario=scenario)
                    for row in result.pop('rows'):
                        row = dict(**identity, **row)
                        if writer is None:
                            writer = csv.DictWriter(handle, fieldnames=list(row))
                            writer.writeheader()
                        writer.writerow(row)
                    scores.append(dict(**identity, **result))
    save(folder/'config.json', config)
    check_freeze()
    save(OUT/'progress.json', dict(configurations=len(list((OUT/'runs').iterdir())), episodes=len(scores)))


def run():
    if (OUT/'started.lock').exists():
        raise RuntimeError('Existing attempt must not be overwritten or restarted')
    (OUT/'started.lock').write_text(str(os.getpid()))
    started = time.time()
    scores = []
    selected = {}
    try:
        for info in ('local','report_mean'):
            costs = []
            for z in range(20):
                name = f'{info}_z{z:02}'
                evaluate(dict(name=name,z=z,information=info), scores)
                shock = [x['cost'] for x in scores if x['config']==name and x['scenario']=='shock']
                costs.append((float(np.mean(shock)), z))
            selected[info] = min(costs)[1]
        history = json.loads((OUT/'inputs/normal_initial_history.json').read_text())['values']
        for label,z in [('reference',8),('selected',selected['local'])]:
            evaluate(dict(name=f'{label}_floor',z=z,rounding='floor'),scores)
            evaluate(dict(name=f'{label}_normal_history',z=z,initial_history=history),scores)
        check_freeze()
        save(OUT/'scores.json',scores)
        existing = []
        for seed in range(11,16):
            for batch in (1,6):
                values=json.loads((OLD/f'runs/seed{seed}_batch{batch:02}/episodes.json').read_text())
                existing.extend(dict(seed=seed,batch=batch,**value) for value in values)
        save(OUT/'historical_comparison.json',existing)
        summary = {}
        for name in sorted({x['config'] for x in scores}):
            summary[name] = {scenario:float(np.mean([x['cost'] for x in scores if x['config']==name and x['scenario']==scenario])) for scenario in ('base','shock')}
        save(OUT/'summary.json',dict(development_only=True, selected_z=selected,costs=summary,
             historical_costs={g:{s:float(np.mean([x['cost'] for x in existing if x['group']==g and x['scenario']==s])) for s in ('base','shock')} for g in ('happo','online_feedback')},
             episodes=len(scores),node_periods=len(scores)*600,api_calls=0,seconds=time.time()-started))
        save(OUT/'completed.json',dict(episodes=len(scores),node_periods=len(scores)*600,api_calls=0))
    except Exception:
        save(OUT/'failed.json',dict(traceback=traceback.format_exc(),episodes_finished=len(scores)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--register',action='store_true')
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    if args.register: register()
    if args.run: run()
