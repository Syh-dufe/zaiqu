"""Continue a registered cohort after diagnosed audit-import failure, without rerolls."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'results/joint_baseline_confirmation/audit_import_recovery_v1'
PROTOCOL=ROOT/'docs/superpowers/plans/2026-10-05-joint-baseline-audit-import-recovery.md'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value)
    return value


b=module('registered_joint_batch_recovery',ROOT/'experiments/joint_baseline_confirmation/batch.py')
a=module('registered_joint_exact_analysis',ROOT/'experiments/joint_baseline_confirmation/analyze.py')
# The old driver imports this generic name after its runner prepends other
# experiment directories. Bind it explicitly without editing frozen sources.
sys.modules['analyze']=a


def provenance():
    assert sys.modules['analyze'] is a
    assert Path(a.__file__).resolve()==(ROOT/'experiments/joint_baseline_confirmation/analyze.py').resolve()
    return {str(p):b.digest(p) for p in (Path(__file__),PROTOCOL,
        b.OUTPUT/'failed.json',b.OUTPUT/'error.log',b.OUTPUT/'freeze.json',b.OUTPUT/'manifest.json',b.OUTPUT/'preflight.json')}


def first_audit(manifest):
    failure=b.read(b.OUTPUT/'failed.json')
    assert failure['failure']=='AttributeError' and failure['detail']=="module 'analyze' has no attribute 'audit_raw'"
    assert failure['completed_runs']==[] and not (b.OUTPUT/'completed.json').exists()
    directory=b.OUTPUT/'runs/seed11_batch01'
    assert sorted(p.name for p in (b.OUTPUT/'runs').iterdir())==['seed11_batch01']
    result=b.audit_child(directory,manifest['input_batches'][0],11)
    assert result['completed']['calls']==len(result['calls'])==34
    return dict(seed=11,batch=1,run_label='seed11_batch01',episodes=24,node_periods=14400,
                completed_sha256=b.digest(directory/'completed.json'),input_sha256=manifest['input_batches'][0]['sha256'],
                runtime_failures=result['runtime_failures'],reused_completed_task=True)


def register():
    assert not OUTPUT.exists(),'Preserve prior recovery registration'
    manifest=b.verify_registration(b.OUTPUT)
    original_wrong=module('joint_wrong_import_diagnostic',ROOT/'experiments/online_llm/analyze.py')
    assert not hasattr(original_wrong,'audit_raw')
    first=first_audit(manifest)
    hashes=provenance()
    raw={str(p):b.digest(p) for p in (b.OUTPUT/'runs/seed11_batch01').rglob('*') if p.is_file()}
    OUTPUT.mkdir(parents=True)
    b.write(OUTPUT/'registration.json',dict(status='passed_no_api_audit_recovery',hashes=hashes,reused_task=first,
        completed_task_hashes=raw,original_registration=str(b.OUTPUT),original_manifest_sha256=b.digest(b.OUTPUT/'manifest.json'),
        simulation_source_unchanged=True,new_inputs=False,new_api_calls=0,first_task_api_calls_preserved=34,
        remaining_tasks=49,original_caps_and_statistics_unchanged=True,
        root_cause='Runner prepends online_llm to sys.path; generic import analyze resolves to online_llm/analyze.py.',
        repair='Explicit file-path load and deterministic analyze module binding only; original runner/source/data untouched.'))
    print('RECOVERY_REGISTERED first task 24/14400 audited; API0; remaining49',flush=True)


def verify():
    record=b.read(OUTPUT/'registration.json')
    assert provenance()==record['hashes']
    assert all(b.digest(Path(p))==sha for p,sha in record['completed_task_hashes'].items())
    manifest=b.verify_registration(b.OUTPUT)
    assert b.digest(b.OUTPUT/'manifest.json')==record['original_manifest_sha256']
    return record,manifest


def run():
    record,manifest=verify()
    assert not any((OUTPUT/n).exists() for n in ('launch.json','failed.json','completed.json')),'Refuse duplicate continuation'
    with (OUTPUT/'launch.json').open('x',encoding='utf-8') as f:json.dump(dict(pid=os.getpid(),started=time.time()),f,indent=2)
    first=record['reused_task'];finished={'seed11_batch01':first};attempts=[]
    b.write(OUTPUT/'progress.json',dict(status='running',completed_runs=list(finished.values())))
    try:
        for seed in b.SEEDS:
            for entry in manifest['input_batches']:
                verify();task=f'seed{seed}_batch{entry["batch"]:02d}'
                if task in finished:continue
                retry=0
                while True:
                    calls=b.all_recorded_calls(b.OUTPUT)
                    first_calls=[c for c in calls if '_quota_recovery' not in c['run']]
                    assert len(calls)+64<=b.TOTAL_HTTP_CAP and sum(c.get('attempt')==1 for c in calls)+32<=b.TOTAL_SEMANTIC_CAP
                    if retry==0:
                        assert len(first_calls)+64<=b.FIRST_PASS_HTTP_CAP and sum(c.get('attempt')==1 for c in first_calls)+32<=b.FIRST_PASS_SEMANTIC_CAP
                    label=task if retry==0 else f'{task}_quota_recovery{retry}'
                    directory=b.OUTPUT/'runs'/label
                    assert not directory.exists(),'Refuse overwrite'
                    command=[sys.executable,'-u',str(b.RUNNER),'--run-name',label,'--input-file',entry['path'],
                             '--training-directory',str(b.training(seed)),'--operator-library',str(b.LIBRARY),'--output-root',str(b.OUTPUT/'runs')]
                    b.write(OUTPUT/'progress.json',dict(status='running',current_task=task,attempt=retry+1,completed_runs=list(finished.values())))
                    with (b.OUTPUT/f'{label}.log').open('x',encoding='utf-8') as log:
                        proc=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                    if proc.returncode==0:break
                    fatal=b.fatal_http(directory)
                    attempts.append(dict(task=task,label=label,exit_code=proc.returncode,fatal_http=fatal,log_sha256=b.digest(b.OUTPUT/f'{label}.log')))
                    b.write(OUTPUT/'attempts.json',attempts)
                    if fatal=='HTTP_402' and retry==0:
                        b.wait_for_balance(OUTPUT,task,1);retry=1;continue
                    raise RuntimeError(f'{task} failed: {fatal or "program/audit error"}; preserve and diagnose')
                result=b.audit_child(directory,entry,seed)
                done=result['completed']
                finished[task]=dict(seed=seed,batch=entry['batch'],run_label=label,episodes=24,node_periods=14400,
                    completed_sha256=b.digest(directory/'completed.json'),input_sha256=entry['sha256'],runtime_failures=done['runtime_failures'])
                b.write(OUTPUT/'progress.json',dict(status='running',completed_runs=list(finished.values())))
                verify()
        summary=b.summarize(b.OUTPUT,manifest,finished)
        b.write(OUTPUT/'completed.json',dict(status='completed',episodes=summary['episodes'],node_periods=summary['node_periods'],
            original_summary_sha256=b.digest(b.OUTPUT/'summary.json'),first_task_reused_without_api_rerun=True))
        b.write(OUTPUT/'progress.json',dict(status='completed',completed_runs=list(finished.values())))
        print('REGISTERED_COHORT_COMPLETED',json.dumps(summary['primary']),flush=True)
    except Exception as exc:
        b.write(OUTPUT/'failed.json',dict(error=type(exc).__name__,detail=str(exc),completed_runs=list(finished.values()),
            original_outputs_preserved=True,no_blind_restart=True))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--register',action='store_true');parser.add_argument('--run',action='store_true')
    args=parser.parse_args();assert args.register!=args.run
    register() if args.register else run()
