"""Resume the registered batch after explicit recharge, preserving every attempt."""
from pathlib import Path
import inspect
import importlib.util
import hashlib
import json
import os
import sys
import argparse

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'experiments/submission_required_driver/batch.py'
spec = importlib.util.spec_from_file_location('registered_required_driver', SOURCE)
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
RECOVERY = driver.OUTPUT / 'recharge_resume_v1'

def prepare():
    driver.key_from_user()
    manifest, freeze = driver.verify()
    progress = driver.read(driver.OUTPUT / 'progress.json')
    assert progress['status'] == 'waiting_for_balance'
    assert driver.balance_available(), 'Balance unavailable'
    finished = progress['completed_tasks']
    for item in finished:
        directory = driver.OUTPUT / 'runs' / item['label']
        assert driver.digest(directory/'completed.json') == item['completed_sha256']
        assert driver.digest(directory/'audit.json') == item['audit_sha256']
        audit = driver.read(directory/'audit.json')
    attempts = driver.read(driver.OUTPUT / 'attempts.json')
    assert attempts[-1]['fatal'] == 'HTTP_402'
    pending = progress['current_task']
    assert attempts[-1]['label'] == pending and '_quota_recovery' not in pending
    assert not (driver.OUTPUT/'runs'/(pending+'_quota_recovery1')).exists()
    code = inspect.getsource(driver.run)
    replacements = [
        ("with (OUTPUT/'started.lock').open('x')", "with (RECOVERY/'started.lock').open('x')"),
        ("write(OUTPUT/'launch.json'", "write(RECOVERY/'launch.json'"),
        ("finished=[];attempts=[]", "finished=RECOVERED_FINISHED.copy();attempts=RECOVERED_ATTEMPTS.copy()"),
        ("phase_finished=[]", "\n            if (OUTPUT/f'{phase}_completed.json').exists():continue\n            phase_finished=[t for t in finished if t['phase']==phase]"),
        ("verify();retry=0", "\n                if any(t['task']==task['task'] for t in finished):continue\n                verify();retry=1 if task['task']==RECOVERED_PENDING else 0"),
        ("write(OUTPUT/'failed.json'", "write(RECOVERY/'failed.json'"),
    ]
    for before, after in replacements:
        assert code.count(before) == 1, before
        code = code.replace(before, after)
    compile(code, str(__file__), 'exec')
    return code, finished, attempts, pending

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['check','run']);args=parser.parse_args()
    code, finished, attempts, pending = prepare()
    if args.action == 'check':
        RECOVERY.mkdir(exist_ok=False)
        driver.write(RECOVERY/'registration.json',dict(original_source_sha256=driver.digest(SOURCE),recovery_source_sha256=driver.digest(Path(__file__)),adapted_run_sha256=hashlib.sha256(code.encode()).hexdigest(),pending=pending,reused_tasks=finished,prior_attempts=attempts,explicit_recharge_authorized=True,same_registered_retry_and_budget=True,changes='Resume audited tasks and immediately take the previously registered single quota recovery; skip completed phases; separate launcher/failure records.'))
        print('RECOVERY_CHECK_PASSED',len(finished),pending)
    else:
        registration=driver.read(RECOVERY/'registration.json')
        assert registration['recovery_source_sha256']==driver.digest(Path(__file__))
        assert registration['adapted_run_sha256']==hashlib.sha256(code.encode()).hexdigest()
        driver.__dict__.update(RECOVERY=RECOVERY,RECOVERED_FINISHED=finished,RECOVERED_ATTEMPTS=attempts,RECOVERED_PENDING=pending)
        exec(code,driver.__dict__)
        driver.run()
