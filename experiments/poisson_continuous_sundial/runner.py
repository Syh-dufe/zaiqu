"""Continuous report-synchronized Sundial predictions and periodic LLM refresh."""
import argparse,copy,csv,hashlib,importlib.util,inspect,json,math,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
OUT=ROOT/'results/poisson_continuous_sundial_v4/development_v1'
OLD=ROOT/'experiments/poisson_full_mechanism/runner.py'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
r=module('continuous_sundial_frozen_full_runner',OLD)
r.OUT=OUT
GENERATE_AT=(19,64,109,154)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def verify():
 r.ref.verify()
 reg=read(OUT/'registration.json')
 for path,digest in reg['files'].items():assert sha(ROOT/path)==digest,path
 return reg

def controller_source():
 original=r.original.EventController
 source=inspect.getsource(original)
 def replace(a,b,count=1):
  nonlocal source
  assert source.count(a)==count,a[:100]
  source=source.replace(a,b)
 replace('''        if notify:
            self.notification = period
        slot = self.notification is not None and (period-self.notification) % 5 == 0
        new_report = public['delivered_through_period'] > self.last_report'''.replace('+',''),
         '''        slot = period in GENERATE_AT
        new_report = public['delivered_through_period'] > self.last_report and public['delivered_through_period'] > 0''')
 replace("notification='emergency has occurred'","notification='routine scheduled policy refresh; no emergency notice or event label'")
 replace("event_allowed = self.method in ('online_feedback','random_screen') or self.events == 0","event_allowed = True")
 replace("self.method in ('online_once','online_feedback','random_screen')","self.method in ('online_once','online_feedback','random_screen','adapted_sundial')")
 replace("elif slot and self.events > 0 and self.method != 'happo':","elif new_report and self.method != 'happo':")
 needle="self.chosen,selection = select(self.candidates,state,visible,orders,proposed,recurrent,actors,paths,5,reports.projection())"
 replace(needle,needle+"\n            self.last_report = public['delivered_through_period']")
 return source

def install_controller():
 source=controller_source()
 (HERE/'controller.py').write_text(source,encoding='utf-8',newline='\n')
 namespace=dict(r.original.__dict__);namespace['GENERATE_AT']=GENERATE_AT
 r.original.GENERATE_AT=GENERATE_AT
 exec(compile(source,str(HERE/'controller.py'),'exec'),namespace)
 r.original.EventController=namespace['EventController']
 r.core.EventController=r.locked.locked.locked.adapter.factory(r.original,r.locked.guard.adapter,r.predictor,r.locked.paths,11,0)
 # Remove event-trigger semantics from model instructions; fixed refresh times are declared.
 text=r.core.SYSTEM
 for old,new in (("Emergency notification gives no start, magnitude or end.","No external emergency notice is used."),
                 ("emergency has occurred","routine scheduled refresh")):
  text=text.replace(old,new)
 r.core.SYSTEM=text+"\nSundial forecasts are updated on every newly delivered report. LLM candidate refreshes use the four fixed schedule points in the registered protocol. No demand shock is injected."
 old_system=r.system
 def system(lead):
  value=old_system(lead)
  return value.replace('No future event magnitude or ending is available.','No external event information is provided.')+"\nSundial forecast refreshes after every newly delivered report; LLM refresh points are decision periods 19, 64, 109 and 154."
 r.system=system

def freeze_sources():
 install_controller()
 return sorted(r.dependency_files() | {Path(__file__),HERE/'controller.py',HERE/'driver.py',HERE/'audit.py',
   ROOT/'docs/superpowers/specs/2026-10-17-poisson-continuous-sundial-design.md',
   ROOT/'docs/superpowers/plans/2026-10-17-poisson-continuous-sundial.md'})

def prepare():
 import numpy as np
 assert not OUT.exists();r.ref.verify()
 paths=r.read(r.TRAIN/'inputs.json')['baseline_development'][:2]
 hashes={}
 for p in freeze_sources():
  assert p.exists(),p
  hashes[p.relative_to(ROOT).as_posix()]=sha(p)
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.mkdir(parents=True,exist_ok=False)
 write(OUT.parent/'inputs.json',dict(paths=paths,source='first two original Poisson10 baseline-development paths',
       seed_indices=[0,1],development_only=True,generated_before_this_protocol=True))
 write(OUT/'inputs.json',dict(base=paths,shock=[]))
 model=r.predictor.base.base.MODEL
 model_files=[p for p in model.rglob('*') if p.is_file()]
 write(OUT/'sundial_model_identity.json',dict(revision=r.predictor.REVISION,parameter_sha256=r.predictor.parameter_hash(),
       cached_files=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(model_files)]))
 hashes[(OUT/'inputs.json').relative_to(ROOT).as_posix()]=sha(OUT/'inputs.json')
 hashes[(OUT/'sundial_model_identity.json').relative_to(ROOT).as_posix()]=sha(OUT/'sundial_model_identity.json')
 hashes[(OUT.parent/'inputs.json').relative_to(ROOT).as_posix()]=sha(OUT.parent/'inputs.json')
 write(OUT/'registration.json',dict(files=hashes,leads=[2,4],model_seeds=[11,12,13,14,15],paths=2,
       episodes=40,node_periods=24000,api_http_cap=320,api_semantic_cap=160,api_calls_only_full_sundial=True,
       generation_decision_periods=list(GENERATE_AT),report_interval=3,continuous_forecast='every newly delivered report',
       no_injected_shock=True,design='development pilot; not independent confirmation'))
 r.ref.archive(ROOT/'docs/artifacts/poisson_continuous_sundial_v4_preregistration',[*freeze_sources(),OUT.parent/'inputs.json',OUT/'registration.json'])

def preflight(lead):
 install_controller();verify()
 # The fixture forces signals at the same registered report times; API replies are synthetic and labelled.
 execute(lead,11,fixture=True)
 d=OUT/'fixtures'/f'L{lead}_seed11'
 r.verify()
 done=read(d/'completed.json')
 assert done['fixture'] and done['http']==0
 return done

def execute(lead,seed,fixture=False):
 install_controller()
 # Preserve the frozen executable body; only the dataset and scenario loop are narrowed.
 source=inspect.getsource(r.execute)
 def replace(a,b,count=1):
  nonlocal source
  assert source.count(a)==count,a
  source=source.replace(a,b)
 replace("data=read(OUT/'inputs.json')","data=read(OUT/'inputs.json')")
 replace("indices=range(1) if fixture else range(3)","indices=range(1) if fixture else range(2)")
 replace("for scenario in ('base','shock'):","for scenario in ('base',):")
 replace("notify=scenario=='shock' and t==data['events'][index]['start_index']+2","notify=False")
 namespace=dict(r.__dict__);namespace.update(OUT=OUT,HERE=HERE,verify=verify,system=r.system)
 namespace['execute']=None
 exec(compile(source,str(HERE/'runner.py'),'exec'),namespace)
 return namespace['execute'](lead,seed,fixture=fixture)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','preflight','run']);p.add_argument('--lead',type=int,choices=(2,4));p.add_argument('--seed',type=int,choices=range(11,16));a=p.parse_args()
 {'prepare':prepare,'preflight':lambda:preflight(a.lead),'run':lambda:execute(a.lead,a.seed)}[a.action]()
