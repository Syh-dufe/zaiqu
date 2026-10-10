"""Unique preregistered upgrade development driver; never modifies prior experiments."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'experiments/online_llm_guard_pool'
sys.path.insert(0,str(HERE))
from runner import core,METHODS,module
auditor=module('guard_pool_driver_auditor',HERE/'audit.py')
audit=auditor.audit
common=module('guard_pool_driver_common',ROOT/'experiments/submission_required/common.py')
read,write,digest=common.read,common.write,common.digest
OLD=ROOT/'results/submission_required/v1'
OUTPUT=ROOT/'results/online_llm_guard_pool/development_v1'
SEEDS=(11,12,13,14,15)

def sources():
    result=core.source_hashes()
    result.update({str(p.relative_to(ROOT)):digest(p) for p in Path(__file__).parent.glob('*.py')})
    return result

def prerequisite():
    done=read(OLD/'completed.json')
    assert done['episodes']==4480 and done['node_periods']==2688000 and done['all_phases_archived']
    # Release is written only after independent review and lossless preservation of
    # successful AND failed attempts, including the recharge recovery.
    release=read(OLD/'upgrade_release.json')
    assert release['independent_audit_passed'] and release['all_attempts_archived']
    assert release['completed_sha256']==digest(OLD/'completed.json')
    assert release['public_report_committed_and_pushed']
    return dict(completed_sha256=digest(OLD/'completed.json'),release_sha256=digest(OLD/'upgrade_release.json'))

def balance():
    request=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY']})
    with urllib.request.urlopen(request,timeout=30) as response:value=json.loads(response.read())
    return value.get('is_available') is True

def register():
    if OUTPUT.exists():raise RuntimeError('Preserve existing registration/output')
    prior=prerequisite()
    fixture=ROOT/'results/online_llm_guard_pool/offline_fixture_v2/preflight_passed.json'
    assert read(fixture)['status']=='passed' and read(fixture)['network_requests']==0
    assert balance(),'No available API balance; do not register or launch'
    inputs={}
    for batch in (1,6):
        path=OLD/'inputs'/f'confirmation{batch:02d}_main.json'
        core.validate_inputs(read(path))
        inputs[str(batch)]=dict(path=str(path),sha256=digest(path),exposed_development_input=True)
    contracts={str(seed):core.contracts(Path(inputs['1']['path']),core.LIBRARY,core.training(seed)) for seed in SEEDS}
    freeze=dict(source_sha256=sources(),training_contracts=contracts,library_sha256=digest(core.LIBRARY),
        system_sha256=hashlib.sha256(core.SYSTEM.encode()).hexdigest(),executable_sha256=digest(sys.executable),
        fixture_sha256=digest(fixture),prior=prior,api_model='deepseek-flash')
    OUTPUT.mkdir(parents=True)
    write(OUTPUT/'freeze.json',freeze)
    tasks=[dict(task=f'development_batch{batch:02d}_seed{seed}',batch=batch,seed=seed,max_http=256,max_semantic=128) for batch in (1,6) for seed in SEEDS]
    write(OUTPUT/'manifest.json',dict(inputs=inputs,tasks=tasks,methods=METHODS,episodes=400,node_periods=240000,
        freeze_sha256=digest(OUTPUT/'freeze.json'),first_caps=[2560,1280],cumulative_caps=[5120,2560],
        development_only=True,no_training=True,gate='combined lower overall cost; no type cost increase; service no worse than original and HAPPO',
        all_negative_cases_retained=True,no_repeated_tuning=True))
    checks=[]
    for task in tasks:
        value=core.contracts(Path(inputs[str(task['batch'])]['path']),core.LIBRARY,core.training(task['seed']))
        assert value['expected_parameter_sha256']==contracts[str(task['seed'])]['expected_parameter_sha256']
        checks.append(dict(task=task['task'],input_sha256=value['input_sha256']))
    write(OUTPUT/'preflight.json',dict(status='passed',checks=checks,paid_calls=0,manifest_sha256=digest(OUTPUT/'manifest.json')))
    print('GUARD_POOL_DEVELOPMENT_REGISTERED; push frozen registration before run',flush=True)

def verify():
    manifest=read(OUTPUT/'manifest.json');freeze=read(OUTPUT/'freeze.json')
    assert digest(OUTPUT/'freeze.json')==manifest['freeze_sha256'] and sources()==freeze['source_sha256']
    assert digest(sys.executable)==freeze['executable_sha256']
    assert prerequisite()==freeze['prior']
    assert hashlib.sha256(core.SYSTEM.encode()).hexdigest()==freeze['system_sha256']
    for entry in manifest['inputs'].values():assert digest(entry['path'])==entry['sha256']
    for contract in freeze['training_contracts'].values():
        for key in ('happo_contract','ippo_contract'):
            for path,sha in contract[key]['hashes'].items():assert digest(path)==sha
    assert digest(core.LIBRARY)==freeze['library_sha256']
    return manifest,freeze

def publish_registration():
    verify()
    target=ROOT/'docs/artifacts/online_llm_guard_pool_development_v1_preregistration'
    if target.exists():raise RuntimeError('Preserve existing publication package')
    target.mkdir(parents=True);files={}
    paths=[OUTPUT/n for n in ('manifest.json','freeze.json','preflight.json')]
    paths += [ROOT/p for p in sources()]
    fixture=ROOT/'results/online_llm_guard_pool/offline_fixture_v2'
    paths += [p for p in fixture.rglob('*') if p.is_file()]
    key=os.environ['DEEPSEEK_API_KEY'].encode()
    for path in paths:
        blob=path.read_bytes();assert key not in blob
        dest=target/(str(path.relative_to(ROOT))+'.gz');dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(gzip.compress(blob,mtime=0));assert gzip.decompress(dest.read_bytes())==blob
        files[str(dest.relative_to(ROOT)).replace('\\','/')]=digest(dest)
    write(target/'manifest.json',dict(files=files,lossless=True,credential_absent=True,paid_calls=0))
    files[str((target/'manifest.json').relative_to(ROOT)).replace('\\','/')]=digest(target/'manifest.json')
    write(OUTPUT/'published_registration.json',dict(manifest_sha256=digest(OUTPUT/'manifest.json'),freeze_sha256=digest(OUTPUT/'freeze.json'),git_files=files))
    print('REGISTRATION_PACKAGE_READY; commit with byte-preserving attributes and push',flush=True)

def summarize(finished,manifest):
    episodes=[];by_type={}
    for task in finished:
        data=read(manifest['inputs'][str(task['batch'])]['path'])
        for e in read(OUTPUT/'runs'/task['label']/'episodes.json'):
            episodes.append(dict(**e,seed=task['seed'],batch=task['batch'],type=data['events'][e['trace']]['type']))
    shock=[e for e in episodes if e['scenario']=='shock']
    def mean(values):return sum(values)/len(values)
    means={m:dict(cost=mean([e['cost'] for e in shock if e['group']==m]),downstream_backlog=mean([e['downstream_backlog'] for e in shock if e['group']==m])) for m in METHODS}
    for kind in sorted({e['type'] for e in shock}):
        by_type[kind]={m:mean([e['cost'] for e in shock if e['group']==m and e['type']==kind]) for m in METHODS}
    gate=(means['guard_pool']['cost']<means['online_feedback']['cost'] and
        all(v['guard_pool']<=v['online_feedback'] for v in by_type.values()) and
        means['guard_pool']['downstream_backlog']<=means['online_feedback']['downstream_backlog'] and
        means['guard_pool']['downstream_backlog']<=means['happo']['downstream_backlog'])
    calls=common.calls_under(OUTPUT/'runs')
    write(OUTPUT/'summary.json',dict(episodes=len(episodes),node_periods=len(episodes)*600,shock_means=means,type_costs=by_type,
        fixed_gate_passed=gate,development_only=True,not_significance_or_generalization=True,
        http=len(calls),semantic=sum(c.get('attempt')==1 for c in calls),usage=common.usage(calls),all_episodes=episodes))

def archive():
    target=OUTPUT/'archive';target.mkdir()
    entries={};key=os.environ['DEEPSEEK_API_KEY'].encode()
    for path in OUTPUT.rglob('*'):
        if not path.is_file() or target in path.parents:continue
        blob=path.read_bytes();assert key not in blob,'Credential in output'
        dest=target/(str(path.relative_to(OUTPUT))+'.gz');dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(gzip.compress(blob,mtime=0));assert gzip.decompress(dest.read_bytes())==blob
        entries[str(dest.relative_to(target))]=dict(source_sha256=digest(path),gzip_sha256=digest(dest))
    write(target/'manifest.json',dict(files=entries,all_attempts_preserved=True,lossless=True,credential_absent=True))

def run():
    manifest,freeze=verify();assert read(OUTPUT/'preflight.json')['status']=='passed'
    # Human-visible registration checkpoint: artifact path and exact blobs must be
    # committed; remote must contain this HEAD before the first paid call.
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0]
    assert revision==remote,'Registration/code must be pushed first'
    registration=read(OUTPUT/'published_registration.json')
    assert registration['manifest_sha256']==digest(OUTPUT/'manifest.json') and registration['freeze_sha256']==digest(OUTPUT/'freeze.json')
    for path,sha in registration['git_files'].items():
        blob=subprocess.check_output(['git','show',f'HEAD:{path}'],cwd=ROOT)
        assert hashlib.sha256(blob).hexdigest()==sha,'Published artifact Git bytes differ'
    with (OUTPUT/'started.lock').open('x') as stream:stream.write(str(os.getpid()))
    write(OUTPUT/'launch.json',dict(pid=os.getpid(),started=time.time(),source_revision=revision))
    finished=[];attempts=[]
    try:
        for task in manifest['tasks']:
            verify();retry=0
            while True:
                calls=common.calls_under(OUTPUT/'runs')
                first=[c for c in calls if '_quota_recovery1' not in Path(c['source']).parent.name]
                assert len(calls)+256<=5120 and sum(c.get('attempt')==1 for c in calls)+128<=2560
                if retry==0:assert len(first)+256<=2560 and sum(c.get('attempt')==1 for c in first)+128<=1280
                label=task['task']+('_quota_recovery1' if retry else '')
                directory=OUTPUT/'runs'/label
                write(OUTPUT/'progress.json',dict(status='running',current_task=label,completed_tasks=finished,total_tasks=10))
                command=[sys.executable,'-u',str(HERE/'runner.py'),'--run-name',label,'--input-file',manifest['inputs'][str(task['batch'])]['path'],
                    '--training-directory',str(core.training(task['seed'])),'--output-root',str(OUTPUT/'runs'),'--methods',*METHODS,'--phase','development']
                with (OUTPUT/f'{label}.log').open('x',encoding='utf-8') as log:
                    process=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                records=read(directory/'calls.json') if (directory/'calls.json').exists() else []
                assert len(records)<=256 and sum(c.get('attempt')==1 for c in records)<=128
                fatal=next((c['failure'] for c in records if c.get('failure') in ('HTTP_401','HTTP_402','HTTP_403')),None)
                attempts.append(dict(label=label,task=task['task'],http=len(records),exit_code=process.returncode,fatal=fatal));write(OUTPUT/'attempts.json',attempts)
                if process.returncode==0:break
                if fatal=='HTTP_402' and retry==0:
                    while not balance():
                        write(OUTPUT/'progress.json',dict(status='waiting_for_balance',current_task=label,completed_tasks=finished))
                        # Background driver wait; no blocking interactive tool wait.
                        time.sleep(1800)
                    retry=1;continue
                raise RuntimeError(f'{label}: {fatal or "program/audit failure"}; preserve and diagnose')
            audit(directory,read(manifest['inputs'][str(task['batch'])]['path']),freeze['training_contracts'][str(task['seed'])]['expected_parameter_sha256'])
            finished.append(dict(task,label=label,audit_sha256=digest(directory/'audit.json')))
            verify();write(OUTPUT/'progress.json',dict(status='running',completed_tasks=finished,total_tasks=10))
        summarize(finished,manifest);archive()
        write(OUTPUT/'completed.json',dict(episodes=400,node_periods=240000,completed_tasks=finished,all_attempts_archived=True,training_updates=0))
        write(OUTPUT/'progress.json',dict(status='completed',completed_tasks=finished,total_tasks=10))
    except Exception as exc:
        write(OUTPUT/'failed.json',dict(error=type(exc).__name__,detail=str(exc),completed_tasks=finished,preserved=True));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('register','publish-registration','verify','run'));args=parser.parse_args()
    common.key_from_user()
    {'register':register,'publish-registration':publish_registration,'verify':verify,'run':run}[args.action]()
