"""Unique frozen development driver; one quota recovery per task, all attempts kept."""
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
import runner
core=runner.core;ROOT=runner.ROOT;HERE=runner.HERE
common=runner.module('timesfm_batch_common',ROOT/'experiments/submission_required/common.py')
analysis=runner.module('timesfm_explicit_analysis',HERE/'analyze.py')
auditor=runner.module('timesfm_explicit_auditor',HERE/'audit.py')
read,write,digest=common.read,common.write,common.digest
OUT=ROOT/'results/timesfm_closed_loop_development/development_v1'
PACKAGE=ROOT/'docs/artifacts/timesfm_closed_loop_development_v1_preregistration'

def balance():
    r=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY']})
    with urllib.request.urlopen(r,timeout=30) as response:value=json.loads(response.read())
    return value.get('is_available') is True

def register():
    assert not OUT.exists(),'Preserve previous registration'
    fixture=ROOT/'results/timesfm_closed_loop_development/no_api_fixture_v1/preflight_passed.json'
    assert read(fixture)['status']=='passed' and read(fixture)['network_requests']==0
    assert read(ROOT/'results/timesfm_path_development/development_v1/completed.json')['gate_passed']
    inputs={str(b):dict(path=str(ROOT/f'results/submission_required/v1/inputs/confirmation{b:02d}_main.json')) for b in (1,6)}
    for x in inputs.values():x['sha256']=digest(x['path']);core.validate_inputs(read(x['path']))
    contracts={str(s):core.contracts(Path(inputs['1']['path']),core.LIBRARY,core.training(s)) for s in range(11,16)}
    prerequisite=read(ROOT/'results/timesfm_forecast_pilot/development_v1/freeze.json')
    dependencies={name:sha for name,sha in prerequisite['sha256'].items() if str(runner.predictor.DEPS) in name.replace('\\','/') or 'zaiqu-timesfm-pilot/model' in name.replace('\\','/')}
    # Include all locked pilot model/dependency bytes by absolute path, without publishing the 925MB checkpoint.
    dependencies={name:sha for name,sha in prerequisite['sha256'].items() if '.cache' in name}
    for path,sha in dependencies.items():assert digest(path)==sha,path
    OUT.mkdir(parents=True)
    freeze=dict(source_sha256=core.source_hashes(),contracts=contracts,dependencies=dependencies,
        system_sha256=hashlib.sha256(core.SYSTEM.encode()).hexdigest(),fixture_sha256=digest(fixture),
        executable_sha256=digest(sys.executable),api_model='deepseek-flash',public_checkpoint_revision=runner.predictor.REVISION)
    write(OUT/'freeze.json',freeze)
    tasks=[dict(task=f'batch{b:02d}_seed{s}',batch=b,seed=s,max_http=256,max_semantic=128) for b in (1,6) for s in range(11,16)]
    write(OUT/'manifest.json',dict(tasks=tasks,inputs=inputs,methods=runner.METHODS,episodes=320,node_periods=192000,first_caps=[2560,1280],cumulative_caps=[5120,2560],freeze_sha256=digest(OUT/'freeze.json'),development_only=True))
    write(OUT/'preflight.json',dict(status='passed',tasks=10,fixture_episodes=32,fixture_node_periods=19200,api_calls=0,automatic_continuation_authorized=True))
    print('REGISTERED_320_EPISODES_NO_COMPLETION_API',flush=True)

def verify():
    m=read(OUT/'manifest.json');f=read(OUT/'freeze.json')
    assert digest(OUT/'freeze.json')==m['freeze_sha256'] and core.source_hashes()==f['source_sha256']
    assert digest(sys.executable)==f['executable_sha256']
    assert hashlib.sha256(core.SYSTEM.encode()).hexdigest()==f['system_sha256']
    for p,sha in f['dependencies'].items():assert digest(p)==sha,p
    for x in m['inputs'].values():assert digest(x['path'])==x['sha256']
    for c in f['contracts'].values():
        for key in ('happo_contract','ippo_contract'):
            for p,sha in c[key]['hashes'].items():assert digest(p)==sha,p
    return m,f

def publish():
    m,f=verify();assert not PACKAGE.exists()
    paths=[ROOT/p for p in f['source_sha256']]+[OUT/n for n in ('manifest.json','freeze.json','preflight.json')]
    paths += [Path(x['path']) for x in m['inputs'].values()]
    paths += [p for p in (ROOT/'results/timesfm_closed_loop_development/no_api_fixture_v1').rglob('*') if p.is_file()]
    PACKAGE.mkdir(parents=True);files={};origins={};key=os.environ['DEEPSEEK_API_KEY'].encode()
    for index,p in enumerate(dict.fromkeys(paths)):
        blob=Path(p).read_bytes();assert key not in blob
        dest=PACKAGE/'files'/f'{index:04d}.gz';dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(gzip.compress(blob,mtime=0));assert gzip.decompress(dest.read_bytes())==blob
        relative=dest.relative_to(ROOT).as_posix();files[relative]=digest(dest);origins[relative]=dict(source=str(p),sha256=digest(p))
    write(PACKAGE/'manifest.json',dict(files=files,origins=origins,credential_absent=True,lossless=True,large_model_public_revision_only=True))
    files[(PACKAGE/'manifest.json').relative_to(ROOT).as_posix()]=digest(PACKAGE/'manifest.json')
    write(OUT/'publication.json',dict(git_files=files,freeze_sha256=digest(OUT/'freeze.json'),manifest_sha256=digest(OUT/'manifest.json')))
    print('PREREGISTRATION_READY_FOR_COMMIT_PUSH',flush=True)

def archive():
    target=OUT/'archive';assert not target.exists();target.mkdir();entries={};key=os.environ['DEEPSEEK_API_KEY'].encode()
    for p in list(OUT.rglob('*')):
        if not p.is_file() or target in p.parents:continue
        blob=p.read_bytes();assert key not in blob
        dest=target/(str(p.relative_to(OUT))+'.gz');dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(gzip.compress(blob,mtime=0));assert gzip.decompress(dest.read_bytes())==blob
        entries[str(dest.relative_to(target))]=dict(source_sha256=digest(p),gzip_sha256=digest(dest))
    write(target/'manifest.json',dict(files=entries,all_attempts_preserved=True,credential_absent=True,lossless=True))

def run():
    m,f=verify();rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0]
    assert rev==remote,'Push preregistration first'
    publication=read(OUT/'publication.json')
    for p,sha in publication['git_files'].items():assert hashlib.sha256(subprocess.check_output(['git','show',f'HEAD:{p}'],cwd=ROOT)).hexdigest()==sha,p
    assert balance(),'No available balance before first task'
    with (OUT/'started.lock').open('x') as stream:stream.write(str(os.getpid()))
    write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),revision=rev));finished=[];attempts=[]
    try:
        for task in m['tasks']:
            verify();retry=0
            while True:
                calls=common.calls_under(OUT/'runs');first=[c for c in calls if '_quota_recovery1' not in Path(c['source']).parent.name]
                assert len(calls)+256<=5120 and sum(c.get('attempt')==1 for c in calls)+128<=2560
                if retry==0:assert len(first)+256<=2560 and sum(c.get('attempt')==1 for c in first)+128<=1280
                label=task['task']+('_quota_recovery1' if retry else '');directory=OUT/'runs'/label
                write(OUT/'progress.json',dict(status='running',current_task=label,completed_tasks=finished,total_tasks=10))
                command=[sys.executable,'-u',str(HERE/'runner.py'),'--seed',str(task['seed']),'--batch',str(task['batch']),'--run-name',label,'--input-file',m['inputs'][str(task['batch'])]['path'],'--training-directory',str(core.training(task['seed'])),'--output-root',str(OUT/'runs'),'--methods',*runner.METHODS,'--phase','development']
                with (OUT/f'{label}.log').open('x',encoding='utf-8') as log:p=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                records=read(directory/'calls.json') if (directory/'calls.json').exists() else []
                assert len(records)<=256 and sum(c.get('attempt')==1 for c in records)<=128
                fatal=next((c.get('failure') for c in records if c.get('failure') in ('HTTP_401','HTTP_402','HTTP_403')),None)
                attempts.append(dict(label=label,http=len(records),exit_code=p.returncode,fatal=fatal));write(OUT/'attempts.json',attempts)
                if p.returncode==0:break
                if fatal=='HTTP_402' and retry==0:
                    while True:
                        write(OUT/'progress.json',dict(status='waiting_for_balance',current_task=label,completed_tasks=finished,total_tasks=10))
                        time.sleep(1800)
                        if balance():break
                    retry=1;continue
                raise RuntimeError(f'{label}: {fatal or "program/audit failure"}; preserve and diagnose')
            auditor.audit(runner,directory,read(m['inputs'][str(task['batch'])]['path']),f['contracts'][str(task['seed'])]['expected_parameter_sha256'])
            finished.append(dict(task,label=label,audit_sha256=digest(directory/'audit.json')));verify()
            write(OUT/'progress.json',dict(status='running',completed_tasks=finished,total_tasks=10))
        summary=analysis.summarize(runner,OUT,finished,common)
        write(OUT/'completed.json',dict(episodes=320,node_periods=192000,completed_tasks=finished,fixed_gate_passed=summary['fixed_gate_passed'],training_updates=0))
        write(OUT/'progress.json',dict(status='completed',completed_tasks=finished,total_tasks=10));archive()
    except Exception as exc:
        write(OUT/'failed.json',dict(error=type(exc).__name__,detail=str(exc),completed_tasks=finished,preserved=True));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('register','publish','verify','run'));opts=parser.parse_args()
    common.key_from_user();{'register':register,'publish':publish,'verify':verify,'run':run}[opts.action]()
