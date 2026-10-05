"""Posthoc Base-stock appendix on completed common paths; no new RL or API."""
import argparse
from contextlib import contextmanager
import csv
import gzip
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'results/joint_baseline_confirmation/confirmation_v1'
OUTPUT=ROOT/'results/base_stock_appendix/posthoc_v1'
PROTOCOL=ROOT/'docs/superpowers/plans/2026-10-05-base-stock-appendix.md'
PHASE='posthoc_additional_baseline_comparison'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


reuse=load('appendix_confirmation_reuse',ROOT/'experiments/base_stock_confirmation/batch.py')
stats=load('appendix_statistics_reuse',ROOT/'experiments/base_stock_confirmation/analyze.py')
read,write,digest=reuse.read,reuse.write,reuse.digest
CONFIGS=reuse.BASE_STOCK_CONFIGS


@contextmanager
def offline():
    original_connect=socket.socket.connect
    original_create=socket.create_connection
    def forbidden(*args,**kwargs):raise RuntimeError('Network/API forbidden for posthoc appendix')
    socket.socket.connect=forbidden
    socket.create_connection=forbidden
    try:yield
    finally:
        socket.socket.connect=original_connect
        socket.create_connection=original_create


def finished_from_summary(summary):
    rows=summary['runs']
    identities={(int(r['seed']),int(r['batch'])) for r in rows}
    expected={(seed,batch) for seed in reuse.SEEDS for batch in range(1,11)}
    if len(rows)!=50 or identities!=expected:
        raise ValueError('Original completed summary must identify exactly fifty unique tasks')
    return {f"seed{r['seed']}_batch{r['batch']:02d}":dict(seed=int(r['seed']),batch=int(r['batch']),
        run_label=r['label'],episodes=24,node_periods=14400,completed_sha256=r['completed_sha256'],
        runtime_failures=r.get('runtime_failures',[])) for r in rows}


def posthoc_summary(summary):
    historical_fields=('api_requests','semantic_requests','token_usage','api_failure_kinds','api_seconds',
                       'call_files','forecast_resources','score_files','calls_with_recorded_numeric_usage')
    for field in historical_fields:
        if field in summary:summary['historical_'+field]=summary.pop(field)
    summary.update(phase=PHASE,posthoc=True,prospective_independent_confirmation=False,
        new_api_requests=0,api_requests=0,semantic_requests=0,new_rl_rollouts=0,new_training_updates=0,
        new_base_stock_episodes=160,new_node_periods=96000,historical_rl_episodes=1200,
        historical_node_periods=720000,historical_api_costs_excluded=False,
        historical_resources_are_previous_experiment_only=True,
        inference='Exploratory additional baseline on already exposed common-confirmation paths; intervals descriptive, not a newly preregistered prospective test.')
    primary=summary['primary']
    primary.pop('stronger_cost_evidence',None)
    primary['exploratory']=True
    primary['prospective_decision']=False
    for comparison in summary.get('comparisons',{}).values():comparison['exploratory']=True
    summary['limitations']='Posthoc addition after the common-confirmation inputs and RL/LLM outcomes were exposed. '+summary.get('limitations','')
    return summary


def source_hashes():
    result=reuse.source_hashes()
    files=list(Path(__file__).parent.glob('*.py'))+[PROTOCOL]
    result.update({str(p):digest(p) for p in files})
    return result


def hash_sources(paths):return {str(p):digest(p) for p in paths}


def register():
    if OUTPUT.exists():raise RuntimeError('Existing appendix must not be overwritten')
    completed=read(OLD/'completed.json')
    assert completed['episodes']==1200 and completed['node_periods']==720000 and completed['completed_runs']==50
    assert digest(OLD/'summary.json')==completed['summary_sha256']
    summary=read(OLD/'summary.json');finished=finished_from_summary(summary)
    old_manifest=read(OLD/'manifest.json')
    assert len(old_manifest['input_batches'])==10
    development=read(ROOT/'results/base_stock_baseline/development_v1/summary.json')
    assert development['selected_z']['local']==2
    paths=[OLD/name for name in ('freeze.json','manifest.json','summary.json','completed.json')]
    paths.extend(Path(e['path']) for e in old_manifest['input_batches'])
    paths.extend(p for directory in (OLD/'runs').iterdir() if directory.is_dir() for p in directory.iterdir() if p.is_file())
    hashes=hash_sources(paths)
    contracts={}
    for seed in reuse.SEEDS:
        entry=old_manifest['input_batches'][0]
        current=reuse.core.contracts(Path(entry['path']),reuse.b.LIBRARY,reuse.b.training(seed),require_key=False)
        previous=entry['contracts'][str(seed)]
        assert {k:v for k,v in current.items() if k!='key_present'}=={k:v for k,v in previous.items() if k!='key_present'}
        contracts[str(seed)]=current
    for item in finished.values():
        directory=OLD/'runs'/item['run_label']
        assert digest(directory/'completed.json')==item['completed_sha256']
        assert item['run_label'].startswith(f"seed{item['seed']}_batch{item['batch']:02d}")
    OUTPUT.mkdir(parents=True)
    write(OUTPUT/'freeze.json',dict(phase=PHASE,posthoc=True,prospective_independent_confirmation=False,
        source_sha256=source_hashes(),original_files_sha256=hashes,runtime=reuse.b.runtime_contract(),
        training_contracts=contracts,library_sha256=digest(reuse.b.LIBRARY),
        original_root=str(OLD),api_requests=0,new_inputs=False,base_stock_configs=CONFIGS,
        original_completed_sha256=digest(OLD/'completed.json'),original_summary_sha256=digest(OLD/'summary.json')))
    manifest=dict(phase=PHASE,posthoc=True,prospective_independent_confirmation=False,
        freeze_sha256=digest(OUTPUT/'freeze.json'),input_batches=old_manifest['input_batches'],finished=finished,
        training_seeds=list(reuse.SEEDS),methods=list(reuse.METHODS),shock_types=list(reuse.PROFILES),
        base_stock_configs=CONFIGS,expected_episodes=1360,expected_rows=816000,expected_node_periods=816000,
        historical_rl_episodes=1200,historical_node_periods=720000,new_episodes=160,new_node_periods=96000,
        new_api_requests=0,new_inputs=False,new_rl_rollouts=0,original_root=str(OLD),
        bootstrap=dict(replicates=20000,seed=20271651,interpretation='posthoc exploratory descriptive intervals'))
    write(OUTPUT/'manifest.json',manifest)
    return manifest


def verify():
    freeze=read(OUTPUT/'freeze.json');manifest=read(OUTPUT/'manifest.json')
    assert digest(OUTPUT/'freeze.json')==manifest['freeze_sha256']
    assert source_hashes()==freeze['source_sha256'] and reuse.b.runtime_contract()==freeze['runtime']
    for path,expected in freeze['original_files_sha256'].items():assert digest(Path(path))==expected,path
    assert digest(reuse.b.LIBRARY)==freeze['library_sha256']
    for seed in reuse.SEEDS:
        contract=reuse.core.contracts(Path(manifest['input_batches'][0]['path']),reuse.b.LIBRARY,
                                     reuse.b.training(seed),require_key=False)
        assert contract==freeze['training_contracts'][str(seed)]
    for entry in manifest['input_batches']:
        assert digest(Path(entry['path']))==entry['sha256']
        reuse.core.validate_inputs(read(Path(entry['path'])))
    return manifest


def copy_original_artifacts():
    copied={}
    for directory in sorted((OLD/'runs').iterdir()):
        if not directory.is_dir():continue
        target=OUTPUT/'runs'/directory.name
        target.mkdir(parents=True,exist_ok=False)
        for source in directory.iterdir():
            if not source.is_file():continue
            destination=target/source.name
            shutil.copyfile(source,destination)
            expected=digest(source)
            assert digest(destination)==expected
            copied[str(destination.relative_to(OUTPUT))]=dict(original=str(source),sha256=expected)
    write(OUTPUT/'copied_historical_artifacts.json',dict(no_rl_rerun=True,new_api_requests=0,files=copied))
    return copied


def evaluate(entry,config):
    directory=OUTPUT/'base_stock'/config['name']/f"batch{entry['batch']:02d}"
    directory.mkdir(parents=True,exist_ok=False)
    write(directory/'config.json',config)
    data=read(Path(entry['path']));scores=[]
    with gzip.open(directory/'periods.csv.gz','wt',encoding='utf-8',newline='') as stream:
        writer=None
        for trace,event in enumerate(data['events']):
            for scenario in ('base','shock'):
                result=reuse.bs.episode(data[scenario][trace],**{k:v for k,v in config.items() if k!='name'})
                identity=dict(group=f"base_stock_{config['name']}",config=config['name'],batch=entry['batch'],
                              trace=trace,type=event['type'],scenario=scenario)
                for row in result.pop('rows'):
                    row=dict(**identity,**row)
                    if writer is None:
                        writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader()
                    writer.writerow(row)
                scores.append(dict(**identity,**result))
    write(directory/'episodes.json',scores)
    write(directory/'completed.json',dict(phase=PHASE,episodes=8,rows=4800,api_requests=0,training_updates=0,
        input_sha256=entry['sha256'],files_sha256={name:digest(directory/name) for name in
        ('config.json','episodes.json','periods.csv.gz')}))
    write(directory/'independent_audit.json',reuse.audit_base_stock(directory,entry,config))


def run():
    manifest=verify()
    with (OUTPUT/'started.lock').open('x',encoding='utf-8') as stream:
        json.dump(dict(pid=os.getpid(),started=time.time(),phase=PHASE),stream)
    with (OUTPUT/'launch.json').open('x',encoding='utf-8') as stream:
        json.dump(dict(pid=os.getpid(),started=time.time(),new_api_requests=0,phase=PHASE),stream)
    begun=time.perf_counter();count=0
    try:
        copied=copy_original_artifacts()
        finished=manifest['finished'];old_audits=[]
        for item in finished.values():
            entry=manifest['input_batches'][item['batch']-1]
            directory=OUTPUT/'runs'/item['run_label']
            result=reuse.audit_child(directory,entry,item['seed'])
            old_audits.append(dict(seed=item['seed'],batch=item['batch'],label=item['run_label'],
                episodes=len(result['episodes']),rows=len(result['rows']),completed_sha256=digest(directory/'completed.json')))
        write(OUTPUT/'reused_rl_audit.json',dict(phase=PHASE,api_requests=0,new_rl_rollouts=0,
            historical_episodes=1200,historical_rows=720000,runs=old_audits))
        for config in CONFIGS:
            for entry in manifest['input_batches']:
                verify();evaluate(entry,config);count+=8
                write(OUTPUT/'progress.json',dict(phase=PHASE,status='running',new_episodes_completed=count,
                    new_node_periods_completed=count*600,new_api_requests=0))
        audits=[]
        for config in CONFIGS:
            for entry in manifest['input_batches']:
                directory=OUTPUT/'base_stock'/config['name']/f"batch{entry['batch']:02d}"
                result=reuse.audit_base_stock(directory,entry,config)
                audits.append(dict(config=config['name'],batch=entry['batch'],**result))
        assert sum(a['rows'] for a in audits)==96000
        for relative,item in copied.items():assert digest(OUTPUT/relative)==item['sha256']
        verify()
        summary=posthoc_summary(stats.summarize(OUTPUT,manifest,finished))
        summary['historical_original_root']=str(OLD)
        summary['historical_original_summary_sha256']=digest(OLD/'summary.json')
        summary['new_compute_wall_seconds_before_summary_write']=time.perf_counter()-begun
        write(OUTPUT/'summary.json',summary)
        verify()
        write(OUTPUT/'independent_audit.json',dict(status='passed',phase=PHASE,new_api_requests=0,
            historical_rl_episodes=1200,new_base_stock_episodes=160,total_episodes=1360,
            historical_rows=720000,new_rows=96000,total_rows=816000,base_stock=audits,
            original_sources_unchanged=True,copied_history_byte_identical=True))
        write(OUTPUT/'completed.json',dict(status='completed',phase=PHASE,posthoc=True,
            prospective_independent_confirmation=False,episodes=1360,node_periods=816000,
            historical_episodes=1200,new_episodes=160,new_node_periods=96000,
            api_requests=0,new_api_requests=0,historical_api_requests=summary['historical_api_requests'],
            summary_sha256=digest(OUTPUT/'summary.json'),audit_sha256=digest(OUTPUT/'independent_audit.json'),
            seconds=time.perf_counter()-begun))
        write(OUTPUT/'progress.json',dict(status='completed',phase=PHASE,new_episodes_completed=160,new_api_requests=0))
        print('POSTHOC_APPENDIX_COMPLETED new_episodes=160 new_rows=96000 API_calls=0',flush=True)
    except Exception as exc:
        write(OUTPUT/'failed.json',dict(failure=type(exc).__name__,detail=str(exc)[:1000],new_episodes_completed=count,
            new_api_requests=0,raw_outputs_preserved=True,no_blind_restart=True))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--register-only',action='store_true');mode.add_argument('--run',action='store_true')
    args=parser.parse_args()
    with offline():
        if args.register_only:
            register();print('POSTHOC_REGISTERED new_inputs=0 new_API_calls=0',flush=True)
        else:run()


if __name__=='__main__':main()
