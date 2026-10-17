"""Independently recompute persisted cost, transition and pairing evidence."""
import csv
import gzip
import json
import numpy as np
from compare import OUT, TRAIN, read, sha, verify, write

def main():
    verify()
    episodes = read(OUT/'episodes.json')
    inputs = read(OUT/'holdout_inputs.json')
    selection = read(OUT/'selection.json')
    assert inputs['selection_sha256'] == sha(OUT/'selection.json')
    validation=read(TRAIN/'inputs.json')['validation']
    totals, sizes, count = {}, {}, 0
    for lead in (2,4):
        previous = None
        with gzip.open(OUT/f'periods_L{lead}.csv.gz','rt',encoding='utf-8',newline='') as f:
            group = []
            for row in csv.DictReader(f):
                group.append(row)
                if len(group) != 3: continue
                a = [{k:(int(v) if k not in ('split','method','old_pipeline','pipeline','target') else v) for k,v in r.items()} for r in group]
                group = []
                first = a[0]
                key = tuple(first[k] for k in ('split','method','lead','seed','path'))
                assert first['t']==sizes.get(key,0)//3
                assert first['demand']==(inputs['paths'] if first['split']=='holdout' else validation)[first['path']][first['t']]
                assert [r['node'] for r in a] == [0,1,2]
                assert all(tuple(r[k] for k in ('split','method','lead','seed','path','t')) == tuple(first[k] for k in ('split','method','lead','seed','path','t')) for r in a)
                if first['t'] == 0:
                    assert all(r['old_inventory']==r['old_backlog']==r['outstanding_before']==0 and json.loads(r['old_pipeline'])==[0]*lead for r in a)
                else:
                    assert previous[0] == key and previous[1][0]['t']+1 == first['t']
                    for old,new in zip(previous[1],a):
                        assert old['inventory']==new['old_inventory'] and old['backlog']==new['old_backlog']
                        assert old['pipeline']==new['old_pipeline'] and old['outstanding_after']==new['outstanding_before']
                demand = [first['demand'], a[0]['action'], a[1]['action']]
                available = [r['old_inventory']+json.loads(r['old_pipeline'])[0] for r in a]
                required = [r['old_backlog']+demand[i] for i,r in enumerate(a)]
                sent = [min(available[i], required[i]) for i in range(3)]
                for i,r in enumerate(a):
                    assert 0 <= r['action'] <= 20
                    assert r['inventory']==available[i]-sent[i] and r['backlog']==required[i]-sent[i]
                    shipment = sent[i+1] if i<2 else r['action']
                    assert r['shipment']==shipment
                    assert json.loads(r['pipeline'])==json.loads(r['old_pipeline'])[1:]+[shipment]
                    assert r['outstanding_after']==r['outstanding_before']+r['action']-shipment
                    assert r['outstanding_after']==(a[i+1]['backlog'] if i<2 else 0)
                    assert r['position']==r['old_inventory']+sum(json.loads(r['old_pipeline']))+r['outstanding_before']-r['old_backlog']
                    if r['method']=='base_stock':
                        target=selection[str(lead)]['selected']['target'][i]
                        assert int(r['target'])==target
                        assert r['action']==min(20,max(0,target-r['position']))
                    cost=r['inventory']+(r['backlog'] if i==0 else 0)
                    assert r['cost']==cost
                    totals[key]=totals.get(key,0)+cost
                    sizes[key]=sizes.get(key,0)+1
                    count+=1
                previous=(key,a)
            assert not group
    assert count==264000 and len(totals)==440
    assert set(sizes.values())=={600}
    identities=set()
    for e in episodes:
        key=tuple(e[k] for k in ('split','method','lead','seed','path'))
        assert key not in identities
        identities.add(key)
        assert abs(totals[key]/600-e['cost'])<1e-12
    rng=np.random.default_rng(20275004)
    model_indices=rng.integers(0,5,size=(20000,5))
    path_indices=rng.integers(0,20,size=(20000,20))
    summary={}
    for lead in (2,4):
        h=np.array([[next(e['cost'] for e in episodes if e['split']=='holdout' and e['lead']==lead and e['method']=='happo' and e['seed']==seed and e['path']==p) for p in range(20)] for seed in range(11,16)])
        b=np.array([next(e['cost'] for e in episodes if e['split']=='holdout' and e['lead']==lead and e['method']=='base_stock' and e['path']==p) for p in range(20)])
        diff=h-b[None,:]
        bootstrap=diff[model_indices[:,:,None],path_indices[:,None,:]].mean(axis=(1,2))
        summary[str(lead)]=dict(base_stock_target=selection[str(lead)]['selected']['target'],base_stock_cost=float(b.mean()),
             happo_mean=float(h.mean()),happo_by_seed={str(s):float(h[i].mean()) for i,s in enumerate(range(11,16))},
             happo_minus_base_stock=float(diff.mean()),relative_percent=float((h.mean()/b.mean()-1)*100),
             descriptive_95_cost_difference_ci=np.quantile(bootstrap,[.025,.975]).tolist(),
             inferior_seed_path_pairs=int((diff>0).sum()),total_seed_path_pairs=100)
    write(OUT/'summary.json',dict(by_lead=summary,api_calls=0,bootstrap_replicates=20000,bootstrap_seed=20275004,
          claim='held-out descriptive comparison of frozen policies; not certified optimality',all_seeds_retained=True))
    verify()
    write(OUT/'independent_audit.json',dict(passed=True,node_periods=count,episodes=len(totals),api_calls=0,
          sources_and_weights_verified=True,transitions_and_costs_recomputed=True,selection_sha256=sha(OUT/'selection.json')))
    print('INDEPENDENT_AUDIT_PASSED',count,flush=True)

if __name__=='__main__': main()
