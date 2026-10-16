"""Descriptive format errors, unchanged grammar, exact prior-response reuse."""
import argparse,ast,copy,hashlib,importlib.util,json,os,socket,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
OLD=ROOT/'results/seeds16_20_fixed_comparison/v2/runs/seed16_merton/calls.json'
def load_module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
legacy=load_module('frozen_extension_runner_v2',ROOT/'experiments/seeds16_20_fixed_comparison/runner.py')
module=legacy.module
ALLOWED={'agent','inventory','backlog','pipeline','arrival','incoming','recent','baseline','growth','happo'}
def diagnostic_compile(original):
 def compile_rule(value):
  try:return original(value)
  except ValueError as e:
   if str(e)!='unknown feature':raise
   names=set()
   for entry in value.get('rules',[]):
    for field in ('when','delta'):
     try:names.update(n.id for n in ast.walk(ast.parse(entry[field],mode='eval')) if isinstance(n,ast.Name))
     except (SyntaxError,KeyError,TypeError):pass
   unknown=sorted(names-ALLOWED-{'min','max','abs'})
   raise ValueError('unknown feature(s): '+','.join(unknown)+'. Allowed input features: '+','.join(sorted(ALLOWED))+'. delta is an output field, never an input variable; reference actual inputs only. Orders are already clipped to [0,20] by the executor.') from e
 return compile_rule
def setup(mode,seed,replay=False,offline=False):
 global core,guard,original,predictor,paths,METHODS,engine
 legacy.setup(mode,seed)
 core,guard,original,predictor,paths,METHODS,engine=legacy.core,legacy.guard,legacy.original,legacy.predictor,legacy.paths,legacy.METHODS,legacy.engine
 compiler=core.compile_rule;fixed=diagnostic_compile(compiler)
 for v in list(sys.modules.values()):
  if v is not None and vars(v).get('compile_rule') is compiler:v.compile_rule=fixed
 old_sources=core.source_hashes
 def sources():
  v=old_sources();files=[*HERE.glob('*.py'),ROOT/'docs/superpowers/plans/2026-10-16-seeds16-20-format-recovery.md']
  v.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return v
 core.source_hashes=sources
 original_contracts=core.contracts
 def contracts(*a,**kw):
  if offline:kw['require_key']=False
  v=original_contracts(*a,**kw);v['source_sha256']=sources();v.update(format_diagnostics='named_unknown_feature_v1',successful_reply_reuse=replay);return v
 core.contracts=contracts
 strict=core.Client;history=core.read(OLD) if replay else [];cache={}
 for c in history:
  key=tuple(c[k] for k in ('group','scenario','trace','event','stage'));cache.setdefault(key,[]).append(c)
 cache={k:v for k,v in cache.items() if any(x['status']=='valid' for x in v)}
 class RecoverClient(strict):
  def __init__(self,out,*a):
   if offline:
    self.output=out;self.system=a[0];self.model=a[1];self.records=[];self.episode_http=0;self.key='offline_fixture_noncredential';self.save()
   else:super().__init__(out,*a)
   self.reused=set()
  def generate(self,context,count,identity,stage):
   key=tuple(identity[k] for k in ('group','scenario','trace','event'))+(stage,)
   if key in cache:
    assert key not in self.reused;self.reused.add(key);prior=cache[key]
    expected=dict(context,candidate_count=count)
    assert all(x['request']['messages'][0]['content']==self.system and json.loads(x['request']['messages'][1]['content'])==expected for x in prior),'Cached API request context differs; stop rather than substitute'
    assert self.episode_http+len(prior)<=16
    for row in prior:
     item=copy.deepcopy(row);item.update(reused_from=str(OLD),reused_source_sha256=hashlib.sha256(OLD.read_bytes()).hexdigest(),new_http=False);self.records.append(item)
    self.episode_http+=len(prior);self.save();valid=next(x for x in prior if x['status']=='valid');values=valid['candidates'];assert len(values)==count
    return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=v,compiled=core.compile_rule(v)) for i,v in enumerate(values)]
   if offline:
    rule={'rules':[{'when':'True','delta':'0'}]};return [dict(id=f"event{identity['event']}_{stage}_{i}",rule=rule,compiled=core.compile_rule(rule)) for i in range(count)]
   return super().generate(context,count,identity,stage)
 core.Client=RecoverClient
 return fixed,compiler
def main():
 p=argparse.ArgumentParser();p.add_argument('--seed',type=int,choices=range(16,21),required=True);p.add_argument('--mode',choices=('merton','sundial'),required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--reference',type=Path);p.add_argument('--offline',action='store_true');a=p.parse_args()
 replay=a.seed==16 and a.mode=='merton';setup(a.mode,a.seed,replay,a.offline)
 assert not a.out.exists();a.out.mkdir(parents=True)
 if a.offline:
  def forbidden(*args,**kw):raise RuntimeError('No network in diagnostic fixture')
  socket.socket.connect=forbidden;socket.create_connection=forbidden
 else:load_module('recovery_secure_key',ROOT/'experiments/submission_required/common.py').key_from_user()
 try:
  contract=core.contracts(a.input,core.LIBRARY,core.training(a.seed));data=core.validate_inputs(core.read(a.input));core.write(a.out/'protocol.json',dict(contract,system=core.SYSTEM,offline_fixture=a.offline));core.write(a.out/'demands.json',data)
  opts=argparse.Namespace(input_file=a.input,operator_library=core.LIBRARY,training_directory=core.training(a.seed),phase='development');core.evaluate(opts,a.out,contract,data)
  auditor=load_module('unchanged_extension_auditor_v2',ROOT/'experiments/seeds16_20_fixed_comparison/audit.py');auditor.audit(sys.modules[__name__],a.out,data,contract['expected_parameter_sha256'],a.reference,a.offline)
  c=core.read(a.out/'calls.json');core.write(a.out/'physical_call_accounting.json',dict(reused_http=sum(bool(x.get('reused_from')) for x in c),new_http=sum(not x.get('reused_from') for x in c),new_semantic=sum(x['attempt']==1 and not x.get('reused_from') for x in c),historical_failed_calls_preserved=True))
  print('FORMAT_RECOVERY_TASK_PASSED',a.seed,a.mode,flush=True)
 except Exception as e:core.write(a.out/'failed.json',dict(type=type(e).__name__,detail=str(e)[:1000],preserved=True));raise
if __name__=='__main__':main()
