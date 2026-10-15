"""Exclusive no-API development batch with independent raw-cost audit."""
import argparse,csv,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
OUT=ROOT/'results/sundial_deterministic_drop/v1'
INPUT=ROOT/'results/sundial_closed_loop_development/development_v2/inputs/stationary.json'
ADAPTER=ROOT/'results/sundial_multiscale_adapter/v1/multiscale24_best.json'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def registration():
 import runner
 files={str(ROOT/p):s for p,s in runner.core.source_hashes().items()}
 for seed in (11,12,13,14,15):
  c=runner.core.contracts(INPUT,runner.core.LIBRARY,runner.core.training(seed))
  files.update(c['model_files']);files.update(c['happo_contract']['hashes'])
  for p in ((ROOT/f'results/sundial_closed_loop_development/development_v2/runs/batch01_seed{seed}' if seed in (11,12) else ROOT/f'results/sundial_focus_completion/v1/runs/seed{seed}_two_types')).rglob('*'):
   if p.is_file():files[str(p)]=sha(p)
 for p in (INPUT,ADAPTER):files[str(p)]=sha(p)
 assert not OUT.exists();OUT.mkdir(parents=True)
 write(OUT/'registration.json',dict(files=files,seeds=[11,12,13,14,15],methods=list(runner.METHODS),episodes=30,rows=18000,api_budget=0,created=time.time(),development_only=True))
def verify():
 r=read(OUT/'registration.json')
 for p,s in r['files'].items():assert sha(Path(p))==s,p
 return r
def audit(directory,seed):
 r=read(directory/'completed.json');assert r['episodes']==6 and r['rows']==3600 and r['calls']==0 and not r['runtime_failures']
 assert read(directory/'calls.json')==[] and read(directory/'forecast_model_checks.json')['unchanged']
 assert all(x['unchanged'] for x in r['parameter_checks'].values())
 with (directory/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
 assert len(rows)==3600 and len({tuple(x[k] for k in ('group','scenario','trace','period','node')) for x in rows})==3600
 data=read(INPUT);old=(ROOT/f'results/sundial_closed_loop_development/development_v2/runs/batch01_seed{seed}' if seed in (11,12) else ROOT/f'results/sundial_focus_completion/v1/runs/seed{seed}_two_types')/'periods.csv'
 with old.open(encoding='utf-8',newline='') as f:ref={(x['scenario'],x['period'],x['node']):x for x in csv.DictReader(f) if x['group']=='original_merton' and x['trace']=='3'}
 for x in rows:
  assert float(x['cost'])==int(x['inventory'])+int(x['backlog'])
  assert 0<=int(x['actual_order'])<=20 and int(x['trace'])==3
  assert int(x['demand'])==data['base' if x['scenario']=='base' else 'shock'][3][int(x['period'])-1]
  if x['scenario']=='base' or int(x['period'])<data['events'][3]['start_index']+3:
   y=ref[x['scenario'],x['period'],x['node']];assert all(x[k]==y[k] for k in ('cost','inventory','backlog','actual_order','policy_order','demand'))
 for info in read(directory/'information_audits.json'):
  assert info['delivered_through_period']<=info['observed_periods']==info['decision_period']-1
 for record in read(directory/'scores.json'):
  assert record['no_llm'] and record['forecast_audit']['provider']==record['group']
  if record.get('generation_event'):
   a=record['candidate_construction'];assert a['initial_score_calls']<=27 and a['refinement_score_calls']==6
  for group_paths in record['forecasts']:
   assert len(group_paths)==3
   assert all(all(0<=v<=20 for v in path) for path in group_paths)
 summary=[]
 for e in read(directory/'episodes.json'):
  local=[float(x['cost']) for x in rows if x['group']==e['group'] and x['scenario']==e['scenario']]
  assert len(local)==600 and abs(sum(local)/600-e['cost'])<1e-10 and e['episode_http']==0
  summary.append(dict(seed=seed,method=e['group'],scenario=e['scenario'],cost=sum(local)/600))
 write(directory/'independent_audit.json',dict(status='passed',rows=3600,api=0,normal_pre_notice_exact=True,cost_recomputed=True,all_models_unchanged=True))
 return summary
def run():
 registration=verify()
 with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time()));summary=[];completed=[]
 try:
  for seed in registration['seeds']:
   verify();label=f'seed{seed}_drop';write(OUT/'progress.json',dict(status='running',task=label,completed=completed))
   import runner
   cmd=[sys.executable,'-u',str(HERE/'runner.py'),'--seed',str(seed),'--run-name',label,'--input-file',str(INPUT),'--training-directory',str(runner.core.training(seed)),'--output-root',str(OUT/'runs'),'--phase','development']
   with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:
    p=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
   assert p.returncode==0,f'{label} failed; preserve outputs'
   summary.extend(audit(OUT/'runs'/label,seed));completed.append(seed);verify();write(OUT/'summary.json',summary)
  write(OUT/'completed.json',dict(episodes=30,rows=18000,api=0,seeds=completed));write(OUT/'progress.json',dict(status='completed',completed=completed))
 except Exception as e:
  write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),completed=completed,preserved=True));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run'));a=p.parse_args();{'register':registration,'run':run}[a.action]()


