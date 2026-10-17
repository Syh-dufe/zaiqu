"""User-requested r=0-only Base-stock evaluation; retrospective, no API."""
import csv
import gzip
import importlib.util
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('same_path_reference',ROOT/'experiments/poisson_shock_base_stock/run.py')
base=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=base
spec.loader.exec_module(base)
ref=base.ref
OUT=ROOT/'results/poisson_paper_range/v1'
HERE=Path(__file__).parent

def verify():
    ref.verify()
    for e in ref.read(OUT/'registration.json')['files']:
        assert ref.sha(ROOT/e['path'])==e['sha256'],e['path']

def prepare():
    ref.verify()
    OUT.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__),ROOT/'experiments/poisson_shock_base_stock/run.py',
      ROOT/'docs/superpowers/specs/2026-10-17-poisson-paper-range-design.md',
      ROOT/'docs/superpowers/plans/2026-10-17-poisson-paper-range.md',
      ref.OUT/'selection.json',ref.OUT/'holdout_inputs.json',ref.OUT/'episodes.json',
      ref.TRAIN/'inputs.json',base.PREVIOUS/'inputs.json',base.PREVIOUS/'episodes.json']
    files += [ROOT/e['path'] for e in ref.read(ref.OUT/'registration.json')['files']]
    ref.write(OUT/'registration.json',dict(files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=ref.sha(p)) for p in sorted(set(files))],episodes=52,node_periods=31200,api=0,review_allowance=0,retrospective=True))
    ref.archive(ROOT/'docs/artifacts/poisson_paper_range_preregistration',[*set(files),OUT/'registration.json'])

def run():
    import torch,json
    torch.set_num_threads(1)
    verify()
    with (OUT/'started.lock').open('x') as f:f.write('no retry or overwrite')
    previous=ref.read(base.PREVIOUS/'episodes.json')
    normal_previous=ref.read(ref.OUT/'episodes.json')
    dev=ref.read(ref.TRAIN/'inputs.json')['baseline_development']
    inputs=ref.read(base.PREVIOUS/'inputs.json')
    holdout=ref.read(ref.OUT/'holdout_inputs.json')['paths']
    selections={}; episodes=[]; table=[]
    with gzip.open(OUT/'periods.csv.gz','wt',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=base.FIELDS);writer.writeheader()
        for lead in (2,4):
            candidates,bounds=ref.grid(lead)
            records=[dict(target=list(t),cost=float(ref.scan_cost(dev,lead,t).mean())) for t,origins in sorted(candidates.items()) if 0 in origins]
            choice=min(records,key=lambda r:(r['cost'],r['target']))
            old=ref.read(ref.OUT/'selection.json')[str(lead)]['paper_grid_best']
            assert choice['target']==old['target'] and abs(choice['cost']-old['cost'])<1e-12
            selections[str(lead)]=dict(selected=choice,candidates=records,bounds=[r for r in bounds if r['review_allowance']==0])
            wrappers,history=ref.install(lead,OUT/f'unused_training_demands_L{lead}.jsonl')
            try:
                env=wrappers.Env()
                for scenario,paths in [('holdout',holdout),('base',inputs['base']),('shock',inputs['shock'])]:
                    vector=ref.scan_cost(paths,lead,choice['target'])
                    for trace,path in enumerate(paths):
                        row=ref.episode(env,path,lead,'base_stock',-1,trace,scenario,writer=writer,target=choice['target'])
                        assert abs(row['cost']-float(vector[trace]))<1e-12
                        episodes.append(row)
                        item=dict(lead=lead,scenario=scenario,trace=trace,base_stock=row['cost'])
                        if scenario=='holdout':
                            matches=[p for p in normal_previous if p['split']=='holdout' and p['method']=='happo' and p['lead']==lead and p['path']==trace]
                            assert sorted(p['seed'] for p in matches)==list(range(11,16))
                            assert all(p['demand_sha256']==row['demand_sha256'] for p in matches)
                            item['happo']=sum(p['cost'] for p in matches)/5
                        else:
                            for group in ('happo','full_sundial'):
                                matches=[p for p in previous if p['lead']==lead and p['scenario']==scenario and p['trace']==trace and p['group']==group]
                                assert sorted(p['seed'] for p in matches)==list(range(11,16))
                                item[group]=sum(p['cost'] for p in matches)/5
                        table.append(item)
            finally:history.close()
    ref.write(OUT/'selection.json',selections)
    ref.write(OUT/'episodes.json',episodes)
    with gzip.open(OUT/'periods.csv.gz','rt',encoding='utf-8') as f:rows=list(csv.DictReader(f))
    assert len(episodes)==52 and len(rows)==31200
    assert len({(r['lead'],r['split'],r['path'],r['t'],r['node']) for r in rows})==31200
    for e in episodes:
        subset=[r for r in rows if int(r['lead'])==e['lead'] and r['split']==e['split'] and int(r['path'])==e['path']]
        assert len(subset)==600 and sum(int(r['cost']) for r in subset)/600==e['cost']
        for r in subset:
            assert int(r['cost'])==int(r['inventory'])+(int(r['backlog']) if int(r['node'])==0 else 0)
            position=int(r['old_inventory'])+sum(json.loads(r['old_pipeline']))+int(r['outstanding_before'])-int(r['old_backlog'])
            assert position==int(r['position'])
            assert int(r['action'])==max(0,min(20,int(r['target'])-position))
    verify()
    ref.write(OUT/'summary.json',table)
    ref.write(OUT/'completed.json',dict(episodes=52,node_periods=31200,api=0,scalar_vector_equal=True,raw_audit_passed=True,registration_unchanged=True,old_paper_grid_best_reproduced=True))
    ref.archive(ROOT/'docs/artifacts/poisson_paper_range_completed',list(OUT.glob('*')))
    print(json.dumps(dict(targets={k:v['selected']['target'] for k,v in selections.items()},shock=[r for r in table if r['scenario']=='shock'],holdout=[dict(lead=l,base_stock=sum(r['base_stock'] for r in table if r['lead']==l and r['scenario']=='holdout')/20,happo=sum(r['happo'] for r in table if r['lead']==l and r['scenario']=='holdout')/20) for l in (2,4)]),indent=2))

if __name__=='__main__':{'prepare':prepare,'run':run}[sys.argv[1]]()
