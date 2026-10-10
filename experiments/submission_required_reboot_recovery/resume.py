"""Diagnosed reboot continuation with conservative accounting for unreadable calls."""
import argparse
import hashlib
import importlib.util
import inspect
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'experiments/submission_required_driver/batch.py'
spec=importlib.util.spec_from_file_location('required_reboot_original_driver',SOURCE)
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
RECOVERY=driver.OUTPUT/'reboot_resume_v1'
DIAGNOSIS=ROOT/'results/reboot_diagnosis/20261010_v1/diagnosis.json'
PLAN=ROOT/'docs/superpowers/plans/2026-10-10-required-reboot-recovery.md'
ORIGINAL_RESOURCE_SUMMARY=driver.stats.summarize_resources

def prepare():
    driver.key_from_user();manifest,freeze=driver.verify()
    diagnosis=driver.read(DIAGNOSIS);assert not diagnosis['completed_or_source_mismatches']
    progress=driver.read(driver.OUTPUT/'progress.json');assert progress['status']=='running'
    pending=progress['current_task'];assert pending==diagnosis['current_task']=='confirmation10_main_seed11'
    finished=progress['completed_tasks'];assert len(finished)==47
    for item in finished:
        path=driver.OUTPUT/'runs'/item['label']
        assert driver.digest(path/'audit.json')==item['audit_sha256'] and driver.digest(path/'completed.json')==item['completed_sha256']
        for name,sha in driver.read(path/'audit.json')['raw_sha256'].items():assert driver.digest(path/name)==sha
    damaged=driver.OUTPUT/'runs'/pending
    assert not (damaged/'completed.json').exists() and not (driver.OUTPUT/'runs'/(pending+'_crash_replay1')).exists()
    raw=(damaged/'calls.json').read_bytes();assert raw and raw.count(bytes([0]))==len(raw)
    for item in diagnosis['preserved']:
        assert driver.digest(ROOT/item['path'])==item['sha256'],'Preserved reboot evidence changed'
    task=next(t for t in manifest['tasks'] if t['task']==pending)
    prior=driver.read(driver.OUTPUT/'attempts.json')
    prior.append(dict(task=pending,label=pending,exit_code=None,fatal='computer_reboot',http=None,
        reserved_http_upper_bound=task['max_http'],reserved_semantic_upper_bound=task['max_semantic'],
        usage_unknown=True,partial_excluded_from_performance=True))
    code=inspect.getsource(driver.run)
    replacements=[
        ("with (OUTPUT/'started.lock').open('x')","with (RECOVERY/'started.lock').open('x')"),
        ("write(OUTPUT/'launch.json'","write(RECOVERY/'launch.json'"),
        ("finished=[];attempts=[]","finished=RECOVERED_FINISHED.copy();attempts=RECOVERED_ATTEMPTS.copy()"),
        ("phase_finished=[]","\n            if (OUTPUT/f'{phase}_completed.json').exists():continue\n            phase_finished=[t for t in finished if t['phase']==phase]"),
        ("verify();retry=0","\n                if any(t['task']==task['task'] for t in finished):continue\n                verify();retry=1 if task['task']==RECOVERED_PENDING else 0"),
        ("if '_quota_recovery' not in Path(c['source']).parent.name","if '_quota_recovery' not in Path(c['source']).parent.name and '_crash_replay1' not in Path(c['source']).parent.name"),
        ("label=task['task']+('_quota_recovery1' if retry else '')","label=task['task']+('_crash_replay1' if task['task']==RECOVERED_PENDING else ('_quota_recovery1' if retry else ''))"),
        ("write(OUTPUT/'failed.json'","write(RECOVERY/'failed.json'"),
    ]
    for before,after in replacements:
        assert code.count(before)==1,before;code=code.replace(before,after)
    compile(code,str(__file__),'exec')
    return manifest,code,finished,prior,pending,task

def accounting(root):
    rows=[]
    for path in Path(root).rglob('calls.json'):
        if path.parent.name=='confirmation10_main_seed11':continue
        rows.extend(dict(source=str(path),**record) for record in driver.read(path))
    reservation_source=str(driver.OUTPUT/'runs'/'confirmation10_main_seed11'/'calls.json')
    rows += [dict(source=reservation_source,attempt=1 if i<88 else 2,status='crash_budget_reservation_not_observed_request') for i in range(176)]
    return rows

def resource_summary(root):
    # Reuse original calculations only on readable attempts. The damaged attempt
    # is explicitly reported as unknown, never counted as zero or invented tokens.
    legacy=ORIGINAL_RESOURCE_SUMMARY
    class ReadableRoot:
        def rglob(self,pattern):
            return (p for p in Path(root).rglob(pattern) if 'confirmation10_main_seed11' not in p.parts)
    namespace=dict(legacy.__globals__)
    def readable_calls(_):
        return [r for r in accounting(root) if r.get('status')!='crash_budget_reservation_not_observed_request']
    namespace['calls_under']=readable_calls
    exec(compile(inspect.getsource(legacy),str(__file__),'exec'),namespace)
    result=namespace['summarize_resources'](ReadableRoot())
    result.update(all_attempts_included=False,all_readable_attempts_included=True,
        interrupted_attempt_http_unknown=True,interrupted_attempt_tokens_unknown=True,
        crash_budget_reservation=dict(http=176,semantic=88,not_observed_usage=True),
        preserved_reboot_diagnosis_sha256=driver.digest(DIAGNOSIS))
    return result

def check():
    manifest,code,finished,prior,pending,task=prepare()
    RECOVERY.mkdir(exist_ok=False)
    driver.write(RECOVERY/'registration.json',dict(original_source_sha256=driver.digest(SOURCE),
        recovery_source_sha256=driver.digest(Path(__file__)),plan_sha256=driver.digest(PLAN),diagnosis_sha256=driver.digest(DIAGNOSIS),
        adapted_run_sha256=hashlib.sha256(code.encode()).hexdigest(),reused_tasks=finished,pending=pending,prior_attempts=prior,
        interrupted_task_reserved_http=176,interrupted_task_reserved_semantic=88,interrupted_usage_unknown=True,
        new_inputs=False,new_models=False,prompt_or_selection_changes=False,paid_calls=0,
        remaining_first_and_cumulative_caps_unchanged=True,crash_replay_limit=1))
    print('REBOOT_RECOVERY_REGISTERED; audited completed tasks',len(finished))

def run():
    _,code,finished,prior,pending,task=prepare()
    registration=driver.read(RECOVERY/'registration.json')
    assert registration['recovery_source_sha256']==driver.digest(Path(__file__))
    assert registration['plan_sha256']==driver.digest(PLAN) and registration['diagnosis_sha256']==driver.digest(DIAGNOSIS)
    assert registration['adapted_run_sha256']==hashlib.sha256(code.encode()).hexdigest()
    # Require the public recovery checkpoint to exist in exact Git storage bytes.
    artifact='docs/artifacts/required_reboot_recovery_v1/registration.json'
    assert subprocess.check_output(['git','show','HEAD:'+artifact],cwd=ROOT)==(RECOVERY/'registration.json').read_bytes()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0]
    assert head==remote and driver.balance_available()
    driver.calls_under=accounting
    driver.stats.summarize_resources=resource_summary
    driver.__dict__.update(RECOVERY=RECOVERY,RECOVERED_FINISHED=finished,RECOVERED_ATTEMPTS=prior,RECOVERED_PENDING=pending)
    exec(code,driver.__dict__);driver.run()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('check','run'));args=parser.parse_args()
    {'check':check,'run':run}[args.action]()
