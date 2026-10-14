"""Bind already exposed inputs by fixed index; no new demand or outcome selection."""
import runner
from pathlib import Path
core=runner.core;ROOT=runner.ROOT;OUT=ROOT/'results/sundial_closed_loop_development/development_v2'

def prepare():
 assert not OUT.exists(),'Preserve earlier attempt'
 old=ROOT/'results/sundial_scenario_development/v1'
 for p,sha in core.read(old/'freeze.json')['sha256'].items():assert core.digest(Path(p))==sha,p
 assert core.read(old/'independent_verification.json')['independent_bootstrap']
 fit=core.read(ROOT/'results/sundial_adapter_development/v1/fit_completed.json');assert core.digest(runner.predictor.ADAPTER)==fit['best_sha256']
 inputs=core.read(old/'inputs.json');OUT.mkdir(parents=True);(OUT/'inputs').mkdir();mapping={}
 for batch,bg in enumerate(('stationary','trend','periodic'),1):
  selected=[r for r in inputs if r['background']==bg and r['path_id'].endswith('_1')];assert len(selected)==4
  data=dict(background=bg,batch=batch,base=[r['base'][0]+[0] for r in selected],shock=[r['shock'][0]+[0] for r in selected],events=[r['event'] for r in selected],
    source_path_ids=[r['path_id'] for r in selected],exposed_development=True,nonconsumed_sentinel=0)
  core.validate_inputs(data);path=OUT/'inputs'/f'{bg}.json';core.write(path,data)
  mapping[str(batch)]=dict(background=bg,path=str(path),sha256=core.digest(path))
 dependencies={p:s for p,s in core.read(ROOT/'results/sundial_adapter_development/v1/freeze.json')['sha256'].items() if '.cache' in p}
 for p,s in dependencies.items():assert core.digest(Path(p))==s
 core.write(OUT/'freeze.json',dict(source_sha256=core.source_hashes(),dependencies=dependencies,adapter_sha256=fit['best_sha256'],
   source_inputs_sha256=core.digest(old/'inputs.json'),source_inputs=str(old/'inputs.json'),
   system_sha256=__import__('hashlib').sha256(core.SYSTEM.encode()).hexdigest(),api_model='deepseek-flash',checkpoint_revision=runner.predictor.REVISION))
 tasks=[dict(task=f'batch{b:02d}_seed{s}',batch=b,background=mapping[str(b)]['background'],seed=s,max_http=256,max_semantic=128) for b in (1,2,3) for s in range(11,16)]
 core.write(OUT/'manifest.json',dict(inputs=mapping,tasks=tasks,methods=runner.METHODS,episodes=480,node_periods=288000,first_caps=[3840,1920],cumulative_caps=[7680,3840],freeze_sha256=core.digest(OUT/'freeze.json'),development_only=True))
 print('SUNDIAL_COST_INPUTS_REGISTERED',len(tasks),flush=True)

if __name__=='__main__':prepare()
