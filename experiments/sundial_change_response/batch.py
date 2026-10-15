"""Fixed finite cost calibration, two CPU processes maximum, no paid calls."""
import argparse,concurrent.futures,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent;OUT=ROOT/'results/sundial_change_response/v1'
SOURCE=ROOT/'results/sundial_multiscale_adapter/v1/inputs.json'
KINDS=('single_surge','sustained_surge','double_surge','surge_then_drop')
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def trace_sha(x):return hashlib.sha256(json.dumps(x[:200],separators=(',',':')).encode()).hexdigest()
def register():
 import runner
 assert not OUT.exists();OUT.mkdir(parents=True);inputs=read(SOURCE);bindings={};split_hashes={}
 old=read(ROOT/'results/sundial_closed_loop_development/development_v2/inputs/stationary.json');excluded={trace_sha(x) for k in ('base','shock') for x in old[k]}
 for split,label in (('train','calibration'),('dev','reserved_validation')):
  selected=[next(p for p in inputs if p['path_id']==f'{split}_stationary_{kind}_1') for kind in KINDS]
  data=dict(background='stationary',batch=1,base=[p['base'][0]+[0] for p in selected],shock=[p['shock'][0]+[0] for p in selected],events=[p['event'] for p in selected],source_path_ids=[p['path_id'] for p in selected],nonconsumed_sentinel=0,exposed_development=True,cost_split=label)
  runner.core.validate_inputs(data);hashes={trace_sha(x) for k in ('base','shock') for x in data[k]};assert len(hashes)==8 and not hashes&excluded
  split_hashes[label]=hashes;path=OUT/f'{label}_inputs.json';write(path,data);bindings[str(path)]=sha(path)
 assert not split_hashes['calibration']&split_hashes['reserved_validation']
 files={str(ROOT/p):v for p,v in runner.core.source_hashes().items()};files.update(bindings);files[str(SOURCE)]=sha(SOURCE);files[str(runner.predictor.ADAPTER)]=sha(runner.predictor.ADAPTER)
 for seed in (11,14):
  c=runner.core.contracts(OUT/'calibration_inputs.json',runner.core.LIBRARY,runner.core.training(seed));files.update(c['model_files']);files.update(c['happo_contract']['hashes'])
 candidates=list(runner.predictor.response.CANDIDATES)
 write(OUT/'registration.json',dict(files=files,candidates=candidates,tasks=[dict(seed=s,candidate=c) for c in candidates for s in (11,14)],episodes=80,rows=48000,max_processes=2,api=0,created=time.time(),cost_selection_only=True,reserved_validation_not_run=True))
def verify():
 r=read(OUT/'registration.json')
 for p,s in r['files'].items():assert sha(Path(p))==s,p
 return r
def run():
 import runner
 auditor=runner.module('response_explicit_auditor',HERE/'audit.py');registration=verify()
 with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
 write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),max_processes=2));completed=[];summary=[];pending=iter(registration['tasks']);active={}
 def start(executor,task):
  seed,candidate=task['seed'],task['candidate'];label=f'seed{seed}_{candidate}';verify()
  def execute():
   cmd=[sys.executable,'-u',str(HERE/'runner.py'),'--seed',str(seed),'--candidate',candidate,'--run-name',label,'--input-file',str(OUT/'calibration_inputs.json'),'--training-directory',str(runner.core.training(seed)),'--output-root',str(OUT/'runs'),'--phase','development']
   with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:return subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
  active[executor.submit(execute)]=(task,label)
 def progress():write(OUT/'progress.json',dict(status='running',completed=completed,active=[x[1] for x in active.values()],total_tasks=10))
 try:
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
   for _ in range(2):start(executor,next(pending))
   progress()
   while active:
    finished,_=concurrent.futures.wait(active,return_when=concurrent.futures.FIRST_COMPLETED)
    for future in finished:
     task,label=active.pop(future);assert future.result()==0,f'{label} program failure; preserve'
     summary.extend(auditor.audit(runner,OUT/'runs'/label,task['seed'],task['candidate'],read(OUT/'calibration_inputs.json')));completed.append(task);verify();write(OUT/'summary.json',summary)
    for _ in range(len(finished)):
     task=next(pending,None)
     if task is not None:start(executor,task)
    progress()
  means={c:sum(x['cost'] for x in summary if x['candidate']==c and x['scenario']=='shock')/8 for c in registration['candidates']};winner=min(registration['candidates'],key=lambda c:means[c]);gate=winner!='zero' and means[winner]<=.99*means['zero']
  write(OUT/'selection.json',dict(means=means,winner=winner,gate_passed=gate,cost_reduction_percent=100*(1-means[winner]/means['zero']),validation_not_run=True))
  write(OUT/'completed.json',dict(episodes=80,rows=48000,api=0,tasks=completed));write(OUT/'progress.json',dict(status='completed',completed=completed,total_tasks=10,gate_passed=gate))
 except Exception as e:write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),completed=completed,preserved=True,no_blind_restart=True));raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run'));a=p.parse_args();{'register':register,'run':run}[a.action]()
