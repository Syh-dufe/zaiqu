"""Independent persisted period/API/causal audit for one Poisson paired job."""
import csv
import gzip
import json
import sys
from pathlib import Path

def main(folder):
    root=Path(__file__).resolve().parents[2]
    inputs=json.loads((root/'results/poisson_full_mechanism/v1/inputs.json').read_text(encoding='utf-8'))
    def read(name):return json.loads((folder/name).read_text(encoding='utf-8'))
    protocol=read('protocol.json');done=read('simulation_completed.json');episodes=read('episodes.json')
    lead=protocol['lead'];groups={};total=0
    with gzip.open(folder/'periods.csv.gz','rt',encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):
            key=(row['group'],row['scenario'],int(row['trace']))
            groups.setdefault(key,[]).append(row)
    assert len(groups)==(4 if protocol['fixture'] else 12)
    for (method,scenario,trace),rows in groups.items():
        assert len(rows)==600
        inv=[0]*3;back=[0]*3;pipeline=[[0]*lead for _ in range(3)];cost=0
        for t in range(200):
            triple=rows[t*3:t*3+3]
            assert [int(r['node']) for r in triple]==[0,1,2]
            assert all(int(r['period'])==t+1 for r in triple)
            demand=inputs[scenario][trace][t]
            assert all(int(r['demand'])==demand for r in triple)
            actions=[int(r['actual_order']) for r in triple]
            proposed=[int(r['policy_order']) for r in triple]
            assert all(0<=a<=20 for a in actions+proposed)
            assert all(abs(a-p)<=6 for a,p in zip(actions,proposed))
            if method=='happo':assert actions==proposed
            available=[inv[i]+pipeline[i][0] for i in range(3)]
            requested=[demand+back[0],actions[0]+back[1],actions[1]+back[2]]
            sent=[min(a,r) for a,r in zip(available,requested)]
            inv=[a-s for a,s in zip(available,sent)]
            back=[r-s for r,s in zip(requested,sent)]
            shipments=[sent[1],sent[2],actions[2]]
            pipeline=[pipeline[i][1:]+[shipments[i]] for i in range(3)]
            for i,row in enumerate(triple):
                assert int(row['inventory'])==inv[i] and int(row['backlog'])==back[i]
                assert json.loads(row['pipeline'])==pipeline[i]
                c=inv[i]+(back[i] if i==0 else 0)
                assert int(row['cost'])==c;cost+=c;total+=1
            notice=inputs['events'][trace]['start_index']+2
            expected='' if scenario=='base' or t<notice else str(notice+1)
            assert all(r['notification_period']==expected for r in triple)
        e=next(e for e in episodes if e['group']==method and e['scenario']==scenario and e['trace']==trace)
        assert abs(e['cost']-cost/600)<1e-12
        assert e['generation_events']==(4 if method=='full_sundial' and scenario=='shock' else 0)
    for trace in range(1 if protocol['fixture'] else 3):
        for scenario in ('base','shock'):
            pure=groups[('happo',scenario,trace)];full=groups[('full_sundial',scenario,trace)]
            end=200 if scenario=='base' else inputs['events'][trace]['start_index']+2
            assert [(r['cost'],r['actual_order']) for r in pure[:end*3]]==[(r['cost'],r['actual_order']) for r in full[:end*3]]
        end=inputs['events'][trace]['start_index']
        for method in ('happo','full_sundial'):
            a=groups[(method,'base',trace)];b=groups[(method,'shock',trace)]
            assert [(r['cost'],r['actual_order']) for r in a[:end*3]]==[(r['cost'],r['actual_order']) for r in b[:end*3]]
    information=read('information.json');assert len(information)==len(groups)*200
    for r in information:
        t=r['decision_period']-1
        assert r['delivered_through']==t//3*3 and r['report_age']==t%3
    calls=[] if protocol['fixture'] else read('calls.json')
    assert len(calls)<=48 and sum(c['attempt']==1 for c in calls)<=24
    for c in calls:
        assert c['group']=='full_sundial' and c['scenario']=='shock'
        assert 1<=c['event']<=4 and c['decision_period']>=inputs['events'][c['trace']]['start_index']+3
        assert c['request']['messages'][0]['content']==protocol['system']
    for r in read('reports.json'):
        path=inputs[r['scenario']][r['trace']]
        assert r['demand_total']==sum(path[r['start_period']-1:r['end_period']])
        assert r['available_from_decision_period']==r['end_period']+1
    assert total==done['rows']
    out=dict(passed=True,episodes=len(groups),rows=total,http=len(calls),
             raw_transitions_costs_and_prefixes_verified=True,causal_reports=True,fixture=protocol['fixture'])
    (folder/'independent_audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PAIRED_AUDIT_PASSED',out,flush=True)

if __name__=='__main__':main(Path(sys.argv[1]))
