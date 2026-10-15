"""Three controlled timing cases; identical full six-rule mechanism on both sides."""
import argparse,copy,inspect,json,math,sys
from pathlib import Path
import importlib.util
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('timing_frozen_six',ROOT/'experiments/sundial_six_rules/runner.py')
six=importlib.util.module_from_spec(spec);sys.modules[spec.name]=six;spec.loader.exec_module(six)
core,guard,original,predictor,paths=six.core,six.guard,six.original,six.predictor,six.paths
module=six.module;METHODS=('happo','original_merton','adapted_sundial');core.METHODS=METHODS
SOURCE_INPUT=ROOT/'results/submission_required/v1/inputs/confirmation01_main.json'
OUT=ROOT/'results/sundial_double_timing/development_v1';INPUT=OUT/'inputs.json'
OFFSETS=(-5,10,25)

def prepare():
    assert not OUT.exists();OUT.mkdir(parents=True)
    # Bind these sources before any transformation; no result-driven selection.
    source_hashes=core.source_hashes();base=core.read(SOURCE_INPUT)['base'][2]
    events=[];shock=[]
    for offset in OFFSETS:
        a,b=65+offset,105+offset;v=base.copy()
        intervals=[dict(start=a,end=a+20,factor=1.5),dict(start=b,end=b+20,factor=1.5)]
        for part in intervals:
            for j in range(part['start'],part['end']):v[j]=min(20,math.ceil(1.5*base[j]))
        shock.append(v);events.append(dict(type='double_surge',start_index=a,duration=60,intervals=intervals,timing_offset=offset,
            notification='single onset notification at first interval + 2 periods'))
    data=dict(base=[base.copy() for _ in OFFSETS],shock=shock,events=events,source_trace=2,controlled_offsets=list(OFFSETS),
              exposed_development=True,same_background_path=True)
    validate_inputs(data);core.write(INPUT,data)
    core.write(OUT/'input_preparation.json',dict(source_sha256=source_hashes,source_input=str(SOURCE_INPUT),
        source_input_sha256=core.digest(SOURCE_INPUT),input_sha256=core.digest(INPUT),offsets=list(OFFSETS),no_outcome_selection=True))

def validate_inputs(data):
    base=core.read(SOURCE_INPUT)['base'][2]
    assert len(base)==201 and data['controlled_offsets']==list(OFFSETS)
    assert len(data['base'])==len(data['shock'])==len(data['events'])==3
    for t,offset in enumerate(OFFSETS):
        assert data['base'][t]==base
        a,b=65+offset,105+offset;e=data['events'][t]
        assert e['type']=='double_surge' and e['start_index']==a and e['duration']==60
        assert e['intervals']==[dict(start=a,end=a+20,factor=1.5),dict(start=b,end=b+20,factor=1.5)]
        expected=base.copy()
        for p in e['intervals']:
            for j in range(p['start'],p['end']):expected[j]=min(20,math.ceil(1.5*base[j]))
        assert data['shock'][t]==expected
        assert all(type(v) is int and 0<=v<=20 for v in data['base'][t]+data['shock'][t])
    return data
core.validate_inputs=validate_inputs
old_sources=core.source_hashes
def sources():
    values=old_sources();files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/plans/2026-10-15-sundial-double-timing.md']
    values.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return values
core.source_hashes=sources
old_contracts=core.contracts
def contracts(*a,**kw):
    v=old_contracts(*a,**kw);v.update(methods=list(METHODS),traces=3,api_budget_total=480,rule_limit=6,
        historical_merton_rule_limit=None,historical_merton_reused=False,matched_guard_pool=True,
        timing_offsets=list(OFFSETS),shared_base_path=True,development_only=True,independent_confirmation=False)
    return v
core.contracts=contracts

# Reuse the frozen evaluator body, adapting only trace count and cardinalities.
body=guard.evaluate_source
assert body.count('env.n_eval=4')==1
body=body.replace('env.n_eval=4','env.n_eval=3').replace('range(4)','range(3)').replace('len(METHODS)*8','len(METHODS)*6').replace('len(METHODS)*4800','len(METHODS)*3600')
def evaluate(*a,**kw):
    before=predictor.parameter_hash();ns=dict(core.__dict__);exec(compile(body,str(HERE/'runner.py'),'exec'),ns);ns['evaluate'](*a,**kw)
    after=predictor.parameter_hash();assert before==after
    core.write(a[1]/'forecast_model_checks.json',dict(before=before,after=after,unchanged=True,adapter_sha256=core.digest(predictor.ADAPTER)))
core.evaluate=evaluate
def configure(seed):
    provider=six.locked.locked.adapter.factory(original,guard.adapter,predictor,paths,seed,1)
    def create(group,*a):
        return original.EventController('happo',*a) if group=='happo' else provider(group,*a)
    core.EventController=create
if __name__=='__main__':
    p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=range(11,16),required=True);v,rest=p.parse_known_args()
    configure(v.seed);sys.argv=[sys.argv[0]]+rest;core.main()
