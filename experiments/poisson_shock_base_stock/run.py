"""Fixed-target, same-input deterministic baseline addition; API-free."""
import csv
import gzip
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'results/poisson_shock_base_stock/v1'
PREVIOUS = ROOT/'results/poisson_full_mechanism/network_recovery_v2'
spec = importlib.util.spec_from_file_location('stationary_reference', ROOT/'experiments/poisson_baseline_comparison/compare.py')
ref = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ref
spec.loader.exec_module(ref)
FIELDS = 'split method lead seed path t node demand old_inventory old_backlog old_pipeline outstanding_before position target action shipment outstanding_after inventory backlog pipeline cost'.split()

def verify():
    ref.verify()
    for e in ref.read(OUT/'registration.json')['files']:
        assert ref.sha(ROOT/e['path']) == e['sha256'], e['path']

def prepare():
    ref.verify()
    OUT.mkdir(parents=True, exist_ok=False)
    files = [Path(__file__), ROOT/'docs/superpowers/plans/2026-10-17-poisson-shock-base-stock.md',
             ref.OUT/'selection.json', ref.OUT/'registration.json',
             PREVIOUS/'inputs.json', PREVIOUS/'episodes.json', PREVIOUS/'independent_final_accounting.json']
    files += [ROOT/e['path'] for e in ref.read(ref.OUT/'registration.json')['files']]
    ref.write(OUT/'registration.json', dict(files=[dict(path=p.relative_to(ROOT).as_posix(), sha256=ref.sha(p)) for p in sorted(set(files))], episodes=12, node_periods=7200, api=0, fixed_targets={'2':[34,29,25],'4':[55,49,44]}, descriptive_exposed_paths=True))
    ref.archive(ROOT/'docs/artifacts/poisson_shock_base_stock_preregistration', [*set(files), OUT/'registration.json'])

def run():
    import torch
    torch.set_num_threads(1)
    verify()
    assert not (OUT/'periods.csv.gz').exists()
    inputs = ref.read(PREVIOUS/'inputs.json')
    selected = ref.read(ref.OUT/'selection.json')
    previous = ref.read(PREVIOUS/'episodes.json')
    assert len(previous) == 120
    episodes = []
    with gzip.open(OUT/'periods.csv.gz', 'wt', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for lead in (2,4):
            wrappers, history = ref.install(lead, OUT/f'unused_training_demands_L{lead}.jsonl')
            target = selected[str(lead)]['selected']['target']
            assert target == ({2:[34,29,25],4:[55,49,44]}[lead])
            try:
                env = wrappers.Env()
                for scenario in ('base','shock'):
                    expected = ref.scan_cost(inputs[scenario], lead, target)
                    for trace, path in enumerate(inputs[scenario]):
                        result = ref.episode(env,path,lead,'base_stock',-1,trace,scenario,writer=writer,target=target)
                        assert abs(result['cost']-float(expected[trace])) < 1e-12
                        episodes.append(result)
            finally:
                history.close()
    ref.write(OUT/'episodes.json', episodes)
    with gzip.open(OUT/'periods.csv.gz', 'rt',encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    identities = {(r['lead'],r['split'],r['path'],r['t'],r['node']) for r in rows}
    assert len(rows) == len(identities) == 7200
    for e in episodes:
        subset = [r for r in rows if int(r['lead'])==e['lead'] and r['split']==e['split'] and int(r['path'])==e['path']]
        assert len(subset)==600
        assert sum(int(r['cost']) for r in subset)/600 == e['cost']
        for r in subset:
            assert int(r['cost']) == int(r['inventory'])+(int(r['backlog']) if int(r['node'])==0 else 0)
            pos=int(r['old_inventory'])+sum(json.loads(r['old_pipeline']))+int(r['outstanding_before'])-int(r['old_backlog'])
            assert pos==int(r['position'])
            assert int(r['action'])==max(0,min(20,int(r['target'])-pos))
    table=[]
    for e in episodes:
        line=dict(lead=e['lead'],scenario=e['split'],trace=e['path'],base_stock=e['cost'])
        for group in ('happo','full_sundial'):
            matches=[p for p in previous if p['lead']==e['lead'] and p['scenario']==e['split'] and p['trace']==e['path'] and p['group']==group]
            assert sorted(p['seed'] for p in matches)==list(range(11,16))
            line[group]=sum(p['cost'] for p in matches)/5
        table.append(line)
    verify()
    ref.write(OUT/'summary.json',table)
    ref.write(OUT/'completed.json',dict(episodes=12,node_periods=7200,api=0,vector_scalar_equal=True,raw_cost_and_inventory_position_passed=True,registration_unchanged=True,reused_episodes=120))
    ref.archive(ROOT/'docs/artifacts/poisson_shock_base_stock_completed', list(OUT.glob('*')))
    print(json.dumps(table,indent=2),flush=True)

if __name__ == '__main__':
    {'prepare':prepare,'run':run}[sys.argv[1]]()
