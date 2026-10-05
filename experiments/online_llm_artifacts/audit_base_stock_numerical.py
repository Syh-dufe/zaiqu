"""Post-run numerical diagnosis; frozen original audit remains unchanged."""
"""Independent scalar reconstruction: no policy or author-environment import."""
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import numpy as np
BOUNDARIES=[]

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/base_stock_baseline/development_v1'


def close(actual, expected):
    assert abs(float(actual)-float(expected))<1e-7, (actual,expected)


def verify_episode(rows, demand, config):
    assert len(rows)==600
    inventory=[10.0]*3
    backlog=[0.0]*3
    pipeline=[[10.0]*4 for _ in range(3)]
    unshipped=[0.0]*3
    history=[list(config.get('initial_history',[10.0]*40)) for _ in range(3)]
    pending=[[] for _ in range(3)]
    for t in range(200):
        block=rows[3*t:3*t+3]
        orders=[]
        for i,row in enumerate(block):
            assert int(row['period'])==t and int(row['node'])==i
            mean=statistics.mean(history[i])
            variance=statistics.pvariance(history[i])
            target=4*mean+config['z']*math.sqrt(4*variance)
            position=inventory[i]+sum(pipeline[i])+unshipped[i]-backlog[i]
            rounding=math.floor if config.get('rounding','ceil')=='floor' else math.ceil
            action=max(0,min(20,rounding(target-position)))
            numpy_target=4*float(np.mean(history[i]))+config["z"]*math.sqrt(4*float(np.var(history[i],ddof=0)))
            registered_action=max(0,min(20,rounding(numpy_target-position)))
            if action != registered_action:
                assert abs((target-position)-round(target-position))<1e-10
                assert abs(target-numpy_target)<1e-10
                assert abs(action-registered_action)==1
                BOUNDARIES.append(dict(config=config["name"] if "name" in config else "fixture",batch=row.get('batch'),trace=row.get('trace'),scenario=row.get('scenario'),period=t,node=i,independent_target=target,numpy_target=numpy_target,position=position,independent_action=action,registered_action=registered_action))
                action=registered_action
            for field,value in [('before_inventory',inventory[i]),('before_backlog',backlog[i]),
                                ('mean',mean),('variance',variance),('target',target),
                                ('position',position),('unshipped',unshipped[i]),('action',action)]:
                close(row[field],value)
            assert [float(x) for x in json.loads(row['before_pipeline'])]==pipeline[i]
            orders.append(action)
        local=[demand[t]]+orders[:-1]
        shipped=[min(local[i+1]+backlog[i+1],inventory[i+1]+pipeline[i+1][0]) for i in range(2)]+[orders[2]]
        for i,row in enumerate(block):
            net=inventory[i]+pipeline[i][0]-local[i]-backlog[i]
            inventory[i]=max(net,0)
            backlog[i]=max(-net,0)
            pipeline[i]=pipeline[i][1:]+[shipped[i]]
            unshipped[i]+=orders[i]-shipped[i]
            for field,value in [('demand',local[i]),('newly_shipped',shipped[i]),
                                ('after_unshipped',unshipped[i]),('inventory',inventory[i]),
                                ('backlog',backlog[i]),('cost',inventory[i]+backlog[i])]:
                close(row[field],value)
            if config.get('information','local')=='local':
                history[i]=(history[i]+[float(local[i])])[-40:]
            else:
                pending[i].append(float(local[i]))
                if len(pending[i])==3:
                    value=statistics.mean(pending[i])
                    history[i]=(history[i]+[value]*3)[-40:]
                    pending[i]=[]
        for i in range(2):
            close(unshipped[i],backlog[i+1])
    return statistics.mean([float(x['cost']) for x in rows])


def run():
    freeze=json.loads((OUT/'freeze.json').read_text())
    for path,expected in freeze.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected,path
    manifest=json.loads((OUT/'manifest.json').read_text())
    for item in manifest['input_batches']:
        assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
    scores=json.loads((OUT/'scores.json').read_text())
    lookup={(r['config'],r['batch'],r['trace'],r['scenario']):r for r in scores}
    assert len(lookup)==704
    total=0
    details=[]
    for folder in sorted((OUT/'runs').iterdir()):
        config=json.loads((folder/'config.json').read_text())
        with gzip.open(folder/'periods.csv.gz','rt',encoding='utf-8',newline='') as handle:
            rows=list(csv.DictReader(handle))
        assert len(rows)==9600
        groups={}
        for row in rows:
            key=(config['name'],int(row['batch']),int(row['trace']),row['scenario'])
            groups.setdefault(key,[]).append(row)
        assert len(groups)==16
        for key,episode_rows in groups.items():
            _,batch,trace,scenario=key
            inputs=json.loads((OUT/f'inputs/batch{batch:02}.json').read_text())
            assert all(r['type']==inputs['events'][trace]['type'] for r in episode_rows)
            cost=verify_episode(episode_rows,inputs[scenario][trace],config)
            close(cost,lookup[key]['cost'])
            close(statistics.mean(float(r['backlog']) for r in episode_rows if int(r['node'])==0),lookup[key]['downstream_backlog'])
            total+=len(episode_rows)
        details.append(dict(config=config['name'],episodes=len(groups),node_periods=len(rows)))
    assert total==422400
    summary=json.loads((OUT/'summary.json').read_text())
    for info in ('local','report_mean'):
        candidates=[(statistics.mean(x['cost'] for x in scores if x['config']==f'{info}_z{z:02}' and x['scenario']=='shock'),z) for z in range(20)]
        assert min(candidates)[1]==summary['selected_z'][info]
    for name,value in summary['costs'].items():
        for scenario,cost in value.items():
            close(cost,statistics.mean(x['cost'] for x in scores if x['config']==name and x['scenario']==scenario))
    result=dict(status='passed',episodes=704,node_periods=total,configurations=len(details),
                independent_scalar_state_cost_target=True,
                discrete_action_verification='Independent statistics arithmetic except enumerated boundaries verified against registered NumPy arithmetic',
                freeze_files=len(freeze),details=details,
                numerical_boundary_count=len(BOUNDARIES),numerical_boundaries=BOUNDARIES,
                audit_note="At enumerated integer boundaries verify registered NumPy arithmetic; preserve original strict audit failure")
    (OUT/'independent_audit_v2.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('details','numerical_boundaries')}))


if __name__=='__main__':
    run()
