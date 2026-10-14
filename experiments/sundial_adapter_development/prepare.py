import argparse
from common import ROOT,HERE,OUT,read,write,digest,historical,generate,verify_freeze
def prepare():
 assert not OUT.exists(),'Preserve earlier attempt'
 prior=read(ROOT/'results/sundial_forecast_pilot/development_v1/freeze.json')
 for p,sha in prior['sha256'].items():assert digest(p)==sha,p
 files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/specs/2026-10-14-sundial-adapter-design.md',ROOT/'docs/superpowers/plans/2026-10-14-sundial-adapter.md',ROOT/'experiments/timesfm_path_development/paths.py',ROOT/'experiments/joint_baseline_confirmation/batch.py',ROOT/'external/liu-inventory/envs/generator.py',ROOT/'experiments/deepseek_refinement/reports.py']
 hashes=prior['sha256'].copy();hashes.update({str(p):digest(p) for p in files})
 OUT.mkdir(parents=True);write(OUT/'freeze.json',dict(sha256=hashes,api=0,training_scope='24 adapter parameters only'))
 used=historical();write(OUT/'historical.json',dict(consumed_hashes=sorted(used)))
 cases=generate('development',8,20271801,used)
 for c in cases:c['split']='train' if c['batch']<=6 else 'dev'
 write(OUT/'development_cases.json',cases)
 write(OUT/'prepared.json',dict(train_paths=24,dev_paths=8,cases=len(cases),cases_sha256=digest(OUT/'development_cases.json'),input_sha256=digest(OUT/'development_inputs.json')))
 print('ADAPTER_TRAIN_DEV_INPUTS_PREPARED',flush=True)
def test():
 verify_freeze();fit=read(OUT/'fit_completed.json');assert digest(OUT/'best_adapter.json')==fit['best_sha256']
 assert not (OUT/'test_cases.json').exists()
 used=set(read(OUT/'historical.json')['consumed_hashes'])
 from common import trace_hash
 for data in read(OUT/'development_inputs.json'):
  for s in ('base','shock'):used.update(trace_hash(t) for t in data[s])
 write(OUT/'test_registration.json',dict(adapter_sha256=fit['best_sha256'],before_first_test_generation=True,candidate_seed_start=20271901))
 cases=generate('test',5,20271901,used);write(OUT/'test_prepared.json',dict(paths=20,cases=len(cases),cases_sha256=digest(OUT/'test_cases.json'),input_sha256=digest(OUT/'test_inputs.json')))
 print('FROZEN_ADAPTER_NEW_TEST_INPUTS_PREPARED',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=('development','test'));a=p.parse_args();{'development':prepare,'test':test}[a.phase]()
