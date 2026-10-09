"""Unique serial driver for the approved required experiment package."""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import urllib.error
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'submission_required'))
from common import ROOT,HERE,OUTPUT,SEEDS,TYPES,METHODS,read,write,digest,module,training,key_from_user,calls_under
from audit import audit

PROTOCOL=ROOT/'docs/superpowers/specs/2026-10-09-required-experiments-design.md'
PLAN=ROOT/'docs/superpowers/plans/2026-10-09-required-experiments.md'
DRIVER=Path(__file__).parent
core=module('required_batch_runner',HERE/'run_online.py')
legacy=module('required_old_input_tools',ROOT/'experiments/joint_baseline_confirmation/batch.py')
stats=module('required_exact_cost_analysis',DRIVER/'analyze.py')
PHASES=('development','confirmation','sensitivity')
CAPS={'development':(224,112),'confirmation':(8800,4400),'sensitivity':(8000,4000)}
PILOT=('happo','no_feedback','no_review','first_only','deterministic_search')
SETTINGS=(('strength110',1.10,0),('strength125_timing0',1.25,0),('strength150',1.50,0),('timing_early',1.25,-30),('timing_late',1.25,30))

def balance_available():
    req=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY']})
    with urllib.request.urlopen(req,timeout=30) as response:data=json.loads(response.read())
    return data.get('is_available') is True

def freeze_sources():
    sources=core.source_hashes()
    for p in DRIVER.glob('*.py'):sources[str(p.relative_to(ROOT))]=digest(p)
    for p in (PROTOCOL,PLAN):sources[str(p.relative_to(ROOT))]=digest(p)
    return sources

def transformed(bases,factor,offset,seed,batch):
    shocks=[];events=[]
    for base,t in zip(bases,TYPES):
        parts=[];shock=base.copy()
        for left,right,original in legacy.intervals(t,offset):
            scale=.5 if original<1 else factor
            parts.append(dict(start=left,end=right,factor=scale))
            for i in range(left,right):shock[i]=min(20,math.ceil(scale*base[i])) if scale>1 else math.floor(scale*base[i])
        events.append(dict(type=t,start_index=min(x['start'] for x in parts),duration=max(x['end'] for x in parts)-min(x['start'] for x in parts),intervals=parts,
            timing_offset=offset,nominal_factor=factor,notification='single onset notification plus two periods'))
        shocks.append(shock)
    data=dict(demand_seed=seed,batch=batch,base=bases,shock=shocks,events=events)
    core.validate_inputs(data);return data

def generated(seed):
    import numpy as np
    sys.path.insert(0,str(core.UPSTREAM))
    from envs.generator import merton
    np.random.seed(seed);return [list(map(int,merton(200,20).demand_list)) for _ in TYPES]

def collision_group(configs,historical,accepted):
    paths={};failures=[]
    for setting,data in configs:
        for trace,scenario,path in legacy.input_path_records(data):
            origin=(trace,scenario)
            if path in historical:failures.append(dict(setting=setting,trace=trace,scenario=scenario,kind='historical'))
            if path in accepted:failures.append(dict(setting=setting,trace=trace,scenario=scenario,kind='previous_pair'))
            if path in paths and paths[path][0]!=trace:
                failures.append(dict(setting=setting,trace=trace,scenario=scenario,kind='different_trace_in_group'))
            # Same underlying pair across settings is repeated-measures, not a new independent case.
            paths[path]=origin
    return failures,set(paths)

def register():
    if (OUTPUT/'manifest.json').exists() or (OUTPUT/'freeze.json').exists():raise RuntimeError('Refuse existing registration')
    passed=read(OUTPUT/'offline_fixture/preflight_passed.json');assert passed['status']=='passed'
    assert balance_available(),'API balance unavailable; no new inputs generated'
    source=freeze_sources()
    reference=ROOT/'results/joint_baseline_confirmation/confirmation_v1/inputs/batch01.json'
    old=read(ROOT/'results/joint_baseline_confirmation/confirmation_v1/freeze.json')
    assert old['api_model']=='deepseek-flash'
    contracts={str(seed):core.contracts(reference,core.LIBRARY,training(seed)) for seed in SEEDS}
    import numpy as np
    import torch
    freeze=dict(source_sha256=source,training_contracts=contracts,library_sha256=digest(core.LIBRARY),
        runtime=dict(executable=sys.executable,executable_sha256=digest(sys.executable),python=sys.version,numpy=np.__version__,torch=torch.__version__),
        offline_preflight_sha256=digest(OUTPUT/'offline_fixture/preflight_passed.json'),model='deepseek-flash',
        original_system_sha256=__import__('hashlib').sha256(core.SYSTEM.encode()).hexdigest(),
        caps=CAPS,confirmation_candidates=list(range(20272001,20272051)),sensitivity_candidates=list(range(20272101,20272151)),
        sensitivity_settings=SETTINGS,normal_training_only=True,all_models_retained=True)
    write(OUTPUT/'freeze.json',freeze)
    historical,sources=legacy.historical_traces(OUTPUT)
    accepted=set();inputs={};tasks=[];screen=[]
    def add_input(identity,phase,data):
        path=OUTPUT/'inputs'/f'{identity}.json';write(path,data)
        inputs[identity]=dict(path=str(path),sha256=digest(path),phase=phase)
    pilot=core.read(reference);add_input('development01','development',pilot)
    for seed in (11,12):tasks.append(dict(phase='development',seed=seed,path_batch=1,input_id='development01',methods=list(PILOT),task=f'development_seed{seed}',max_http=112,max_semantic=56))
    for phase,seed_range,required in (('confirmation',range(20272001,20272051),10),('sensitivity',range(20272101,20272151),5)):
        count=0
        for seed in seed_range:
            if count==required:break
            bases=generated(seed)
            if phase=='confirmation':
                offset=-10+2*count
                data=legacy.generated_batch(seed,count)
                assert data['base']==bases
                configs=[('main',data)]
            else:configs=[(name,transformed(bases,factor,offset,seed,count+1)) for name,factor,offset in SETTINGS]
            failures,paths=collision_group(configs,historical,accepted)
            screen.append(dict(phase=phase,seed=seed,accepted=not failures,collisions=failures,
                path_hashes=sorted(legacy.trace_hash(p) for p in paths)))
            if failures:continue
            count+=1;accepted.update(paths)
            for setting,data in configs:
                identity=f'{phase}{count:02d}_{setting}';add_input(identity,phase,data)
                methods=list(METHODS if phase=='confirmation' else ('happo','online_feedback'))
                for model in SEEDS:tasks.append(dict(phase=phase,seed=model,path_batch=count,input_id=identity,methods=methods,setting=setting,
                    task=f'{identity}_seed{model}',max_http=176 if phase=='confirmation' else 64,max_semantic=88 if phase=='confirmation' else 32))
        if count!=required:
            write(OUTPUT/'registration_failed.json',dict(phase=phase,accepted=count,required=required,no_API_calls=True,no_rollouts=True));raise RuntimeError('Fixed candidate sequence exhausted')
    assert freeze_sources()==source,'Source changed while registering'
    write(OUTPUT/'collision_diagnosis.json',dict(historical_source_manifest=sources,historical_paths=len(historical),screen=screen,zero_paths_not_outcome_filtered=True))
    expected=sum(len(t['methods'])*8 for t in tasks)
    assert expected==4480 and len(tasks)==177
    manifest=dict(inputs=inputs,tasks=tasks,expected_episodes=expected,expected_node_periods=expected*600,
        source_freeze_sha256=digest(OUTPUT/'freeze.json'),collision_sha256=digest(OUTPUT/'collision_diagnosis.json'),
        phase_counts={p:sum(len(t['methods'])*8 for t in tasks if t['phase']==p) for p in PHASES},
        phase_first_pass_caps=CAPS,phase_cumulative_caps={p:[2*a for a in pair] for p,pair in CAPS.items()},
        no_training=True,no_test_tuning=True,all_cases_retained=True,bootstrap_seed=20271652,bootstrap_replicates=20000)
    write(OUTPUT/'manifest.json',manifest)
    print('REGISTERED',expected,expected*600,len(tasks),flush=True)

def verify():
    manifest=read(OUTPUT/'manifest.json');freeze=read(OUTPUT/'freeze.json')
    assert digest(sys.executable)==freeze['runtime']['executable_sha256']
    assert digest(OUTPUT/'freeze.json')==manifest['source_freeze_sha256'] and freeze_sources()==freeze['source_sha256']
    assert digest(OUTPUT/'collision_diagnosis.json')==manifest['collision_sha256']
    for entry in manifest['inputs'].values():assert digest(entry['path'])==entry['sha256']
    for contract in freeze['training_contracts'].values():
        for key in ('happo_contract','ippo_contract'):
            for p,sha in contract[key]['hashes'].items():assert digest(p)==sha
    assert digest(core.LIBRARY)==freeze['library_sha256']
    return manifest,freeze

def preflight():
    manifest,freeze=verify();checks=[]
    for seed in SEEDS:
        for phase in PHASES:
            task=next(t for t in manifest['tasks'] if t['seed']==seed and t['phase']==phase) if phase!='development' or seed in (11,12) else None
            if task is None:continue
            core.METHODS=tuple(task['methods'])
            value=core.contracts(Path(manifest['inputs'][task['input_id']]['path']),core.LIBRARY,training(seed))
            assert value['expected_parameter_sha256']==freeze['training_contracts'][str(seed)]['expected_parameter_sha256']
            checks.append(dict(seed=seed,phase=phase,methods=task['methods'],input_sha256=value['input_sha256']))
    core.METHODS=METHODS
    assert __import__('hashlib').sha256(core.SYSTEM.encode()).hexdigest()==freeze['original_system_sha256']
    write(OUTPUT/'preflight.json',dict(status='passed',checks=checks,manifest_sha256=digest(OUTPUT/'manifest.json'),paid_calls=0))
    print('CONTRACT_PREFLIGHT_PASSED',len(checks),flush=True)

def archive_phase(phase,tasks):
    import gzip
    target=OUTPUT/'archive'/phase;target.mkdir(parents=True,exist_ok=True);files={}
    for task in tasks:
        root=OUTPUT/'runs'/task['label']
        for p in root.rglob('*'):
            if not p.is_file():continue
            blob=p.read_bytes();key=os.environ['DEEPSEEK_API_KEY'].encode()
            assert key not in blob,'Credential reflected into raw output'
            dest=target/task['label']/p.relative_to(root);dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():raise RuntimeError('Refuse archive overwrite')
            packed=dest.with_suffix(dest.suffix+'.gz');packed.write_bytes(gzip.compress(blob,mtime=0))
            assert gzip.decompress(packed.read_bytes())==blob
            files[str(packed.relative_to(OUTPUT))]=dict(source_sha256=digest(p),compressed_sha256=digest(packed))
    write(target/'manifest.json',dict(phase=phase,files=files,lossless_sha_verified=True,credential_absent=True))

def run():
    manifest,freeze=verify();assert read(OUTPUT/'preflight.json')['status']=='passed'
    with (OUTPUT/'started.lock').open('x') as stream:stream.write(str(os.getpid()))
    write(OUTPUT/'launch.json',dict(pid=os.getpid(),started=time.time(),manifest_sha256=digest(OUTPUT/'manifest.json')))
    finished=[];attempts=[]
    try:
        for phase in PHASES:
            phase_finished=[]
            for task in [t for t in manifest['tasks'] if t['phase']==phase]:
                verify();retry=0
                while True:
                    all_calls=calls_under(OUTPUT/'runs')
                    phase_calls=[c for c in all_calls if Path(c['source']).parent.name.startswith(phase)]
                    first=[c for c in phase_calls if '_quota_recovery' not in Path(c['source']).parent.name]
                    cap_http,cap_sem=CAPS[phase]
                    assert len(phase_calls)+task['max_http']<=2*cap_http and sum(c.get('attempt')==1 for c in phase_calls)+task['max_semantic']<=2*cap_sem
                    if retry==0:assert len(first)+task['max_http']<=cap_http and sum(c.get('attempt')==1 for c in first)+task['max_semantic']<=cap_sem
                    label=task['task']+('_quota_recovery1' if retry else '');directory=OUTPUT/'runs'/label
                    write(OUTPUT/'progress.json',dict(status='running',phase=phase,current_task=label,completed_tasks=finished,total_tasks=len(manifest['tasks'])))
                    cmd=[sys.executable,'-u',str(HERE/'run_online.py'),'--run-name',label,'--input-file',manifest['inputs'][task['input_id']]['path'],
                        '--training-directory',str(training(task['seed'])),'--output-root',str(OUTPUT/'runs'),'--methods',*task['methods'],'--phase',phase]
                    with (OUTPUT/f'{label}.log').open('x',encoding='utf-8') as log:result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                    calls=read(directory/'calls.json') if (directory/'calls.json').exists() else []
                    failure=next((c['failure'] for c in calls if c.get('failure') in ('HTTP_401','HTTP_402','HTTP_403')),None)
                    attempts.append(dict(task=task['task'],label=label,exit_code=result.returncode,fatal=failure,http=len(calls)))
                    write(OUTPUT/'attempts.json',attempts)
                    if result.returncode==0:break
                    if failure=='HTTP_402' and retry==0:
                        while True:
                            write(OUTPUT/'progress.json',dict(status='waiting_for_balance',current_task=label,completed_tasks=finished))
                            time.sleep(1800)
                            if balance_available():break
                        retry=1;continue
                    raise RuntimeError(f'{label} failed: {failure or "program/audit error"}; preserve and diagnose')
                data=read(manifest['inputs'][task['input_id']]['path'])
                audit(directory,task['methods'],data,freeze['training_contracts'][str(task['seed'])]['expected_parameter_sha256'])
                item=dict(task,label=label,completed_sha256=digest(directory/'completed.json'),audit_sha256=digest(directory/'audit.json'))
                finished.append(item);phase_finished.append(item);verify()
                write(OUTPUT/'progress.json',dict(status='running',phase=phase,completed_tasks=finished,total_tasks=len(manifest['tasks'])))
            summary=stats.summarize(phase,phase_finished,manifest['inputs'])
            archive_phase(phase,phase_finished)
            write(OUTPUT/f'{phase}_completed.json',dict(episodes=summary['episodes'],node_periods=summary['node_periods'],summary_sha256=digest(OUTPUT/f'{phase}_summary.json')))
        assert len(finished)==177
        write(OUTPUT/'completed.json',dict(episodes=manifest['expected_episodes'],node_periods=manifest['expected_node_periods'],completed_tasks=finished,all_phases_archived=True,training_updates=0))
        write(OUTPUT/'progress.json',dict(status='completed',completed_tasks=finished,total_tasks=177))
        print('REQUIRED_EXPERIMENT_PACKAGE_COMPLETED',flush=True)
    except Exception as e:
        write(OUTPUT/'failed.json',dict(error=type(e).__name__,detail=str(e)[:1000],completed_tasks=finished,preserved=True,no_blind_restart=True));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','preflight','run'));args=p.parse_args()
    key_from_user()
    try:{'register':register,'preflight':preflight,'run':run}[args.action]()
    except Exception as e:
        if args.action=='register':write(OUTPUT/'registration_failed.json',dict(error=type(e).__name__,detail=str(e)[:1000],preserved=True))
        raise
