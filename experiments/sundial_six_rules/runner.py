"""Only new response-Sundial runs; historical real-Merton outputs stay read-only."""
import argparse,importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
locked=module('cached_original_live_runner',ROOT/'experiments/sundial_response_live_api/runner.py')
core=locked.core;guard=locked.guard;original=locked.original;predictor=locked.predictor;paths=locked.paths
METHODS=('adapted_sundial',);core.METHODS=METHODS
# Independent version: widen cardinality only, retain native expression grammar.
import inspect
old_compile=core.compile_rule
text=inspect.getsource(old_compile)
assert text.count('<= 4:')==1 and text.count('expected one to four rules')==1
text=text.replace('<= 4:','<= 6:').replace('expected one to four rules','expected one to six rules')
ns=dict(old_compile.__globals__);exec(compile(text,str(HERE/'runner.py'),'exec'),ns);compile_six=ns['compile_rule']
for value in list(sys.modules.values()):
 if value is not None and vars(value).get('compile_rule') is old_compile:value.compile_rule=compile_six
base_module=module
def module(name,path):
 value=base_module(name,path)
 if Path(path).resolve()==(ROOT/'experiments/deepseek_pilot/rules.py').resolve():value.compile_rule=compile_six
 return value
assert core.SYSTEM.count('contains1..4 ordered first-match rules')==1
assert core.SYSTEM.count('one to four valid DSL rules')==1
OLD_SYSTEM=core.SYSTEM
core.SYSTEM=core.SYSTEM.replace('contains1..4 ordered first-match rules','contains1..6 ordered first-match rules').replace('one to four valid DSL rules','one to six valid DSL rules')
old_sources=core.source_hashes
def sources():
 v=old_sources();files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/plans/2026-10-15-sundial-six-rules.md']
 v.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return v
core.source_hashes=sources;old_contracts=core.contracts
def contracts(*args,**kwargs):
 v=old_contracts(*args,**kwargs);v.update(methods=list(METHODS),api_budget_total=128,historical_merton_reused=True,matched_guard_pool=True,rule_limit=6,historical_merton_rule_limit=4,predictor_only_comparison=False);return v
core.contracts=contracts
def configure(seed):locked.configure(seed)
if __name__=='__main__':
 p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=(11,12),required=True);a,rest=p.parse_known_args();configure(a.seed);sys.argv=[sys.argv[0]]+rest;core.main()
