"""Independent raw transition, cadence, cost, and forecast audit."""
import csv,gzip,json,sys
from pathlib import Path
def audit(folder):
 folder=Path(folder);root=Path(__file__).resolve().parents[2]
 protocol=json.loads((folder/'protocol.json').read_text(encoding='utf-8'))
 data=json.loads((root/'results/poisson_continuous_sundial_v4/development_v1/inputs.json').read_text(encoding='utf-8'))
 episodes=json.loads((folder/'episodes.json').read_text(encoding='utf-8'))
 groups={}
 with gzip.open(folder/'periods.csv.gz','rt',encoding='utf-8',newline='') as f:
  for r in csv.DictReader(f):groups.setdefault(r['group'],[]).append(r)
 assert set(groups)=={'happo','full_sundial'}
 ntraces=1 if protocol['fixture'] else 2
 assert len(episodes)==2*ntraces and all(len(v)==600*ntraces for v in groups.values())
 costs={}
 for method,allrows in groups.items():
  for trace in range(ntraces):
   rows=[r for r in allrows if int(r['trace'])==trace]
   inv=[0]*3;back=[0]*3;pipe=[[0]*protocol['lead'] for _ in range(3)];total=0
   for t in range(200):
    tri=rows[t*3:t*3+3];assert [int(r['node']) for r in tri]==[0,1,2]
    d=int(data['base'][trace][t]);assert all(int(r['demand'])==d for r in tri)
    actions=[int(r['actual_order']) for r in tri];proposal=[int(r['policy_order']) for r in tri]
    assert all(0<=x<=20 for x in actions+proposal) and all(abs(a-p)<=6 for a,p in zip(actions,proposal))
    if method=='happo':assert actions==proposal
    avail=[inv[i]+pipe[i][0] for i in range(3)];req=[d+back[0],actions[0]+back[1],actions[1]+back[2]]
    sent=[min(a,q) for a,q in zip(avail,req)];inv=[a-s for a,s in zip(avail,sent)];back=[q-s for q,s in zip(req,sent)]
    shipped=[sent[1],sent[2],actions[2]];pipe=[pipe[i][1:]+[shipped[i]] for i in range(3)]
    for i,row in enumerate(tri):
     assert int(row['inventory'])==inv[i] and int(row['backlog'])==back[i]
     assert json.loads(row['pipeline'])==pipe[i]
     c=inv[i]+(back[i] if i==0 else 0);assert int(row['cost'])==c;total+=c
   ep=next(e for e in episodes if e['group']==method and e['scenario']=='base' and e['trace']==trace)
   assert abs(ep['cost']-total/600)<1e-12
   costs[f'{method}_trace{trace}']=total/600
   assert all(r['notification_period']=='' for r in rows)
 scorefile=json.loads((folder/'scores.json').read_text(encoding='utf-8'))
 full=[r for r in scorefile if r.get('method')=='guard_pool']
 assert sorted(r['decision_period'] for r in full if r.get('generation_event') and r['trace']==0)==[19,64,109,154]
 assert sorted(r['decision_period'] for r in full if r.get('generation_event') and r['trace']==1)==([] if ntraces==1 else [19,64,109,154])
 report_periods=list(range(4,200,3))
 assert all(sorted(r['decision_period'] for r in full if r['trace']==trace)==report_periods for trace in range(ntraces))
 assert len(full)==66*ntraces and all(r.get('forecasts') for r in full)
 calls=[] if protocol['fixture'] else json.loads((folder/'calls.json').read_text(encoding='utf-8'))
 assert len(calls)<=16 and all(c['group']=='full_sundial' and c['scenario']=='base' for c in calls)
 out=dict(passed=True,episodes=2*ntraces,rows=1200*ntraces,costs=costs,continuous_report_updates=len(full),scheduled_generation_events=4*ntraces,http=len(calls),api_free_fixture=protocol['fixture'])
 (folder/'independent_audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n')
 print('CONTINUOUS AUDIT PASSED',out,flush=True)
 return out
if __name__=='__main__':audit(sys.argv[1])
