"""Registered three-position, five-model full-mechanism paired evaluation."""
import argparse,gzip,hashlib,importlib.util,json,os,subprocess,sys,time,urllib.request,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=ROOT/'experiments/sundial_double_timing'
def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);v=importlib.util.module_from_spec(s);sys.modules[name]=v;s.loader.exec_module(v);return v
runner=module('registered_double_timing_runner',HERE/'runner.py');core=runner.core
common=module('timing_protected_common',ROOT/'experiments/submission_required/common.py')
auditor=module('timing_explicit_raw_audit',HERE/'audit.py')
read,write,sha=common.read,common.write,common.digest
OUT=runner.OUT;FIXTURE=OUT.parent/'no_api_fixture_v1';INPUT=runner.INPUT
PACKAGE=ROOT/'docs/artifacts/sundial_double_timing_preregistration_v1'
def available():
    q=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+os.environ['DEEPSEEK_API_KEY']})
    with urllib.request.urlopen(q,timeout=30) as f:return json.loads(f.read()).get('is_available') is True
def register():
    assert not (OUT/'registration.json').exists() and not PACKAGE.exists()
    assert read(FIXTURE/'preflight_passed.json')['network_requests']==0
    preparation=read(OUT/'input_preparation.json');assert preparation['source_sha256']==core.source_hashes()
    assert preparation['source_input_sha256']==sha(runner.SOURCE_INPUT) and preparation['input_sha256']==sha(INPUT)
    assert runner.predictor.CANDIDATE=='all_half'
    files={str(ROOT/p):h for p,h in core.source_hashes().items()}
    models={}
    for seed in range(11,16):
        c=core.contracts(INPUT,core.LIBRARY,core.training(seed));models[str(seed)]=c
        for name in ('happo_contract','ippo_contract'):files.update(c[name]['hashes'])
    for p in runner.predictor.base.base.MODEL.rglob('*'):
        if p.is_file():files[str(p)]=sha(p)
    evidence=[runner.SOURCE_INPUT,INPUT,OUT/'input_preparation.json',Path(__file__),runner.predictor.ADAPTER,
        ROOT/'results/sundial_change_response_recovery/v1/selection.json']+[p for p in FIXTURE.rglob('*') if p.is_file()]
    for p in evidence:files[str(p)]=sha(p)
    r=dict(files=files,contracts=models,offsets=list(runner.OFFSETS),methods=list(runner.METHODS),seeds=list(range(11,16)),
        input_sha256=sha(INPUT),source_input_sha256=sha(runner.SOURCE_INPUT),rule_limit_both=6,episodes=90,rows=54000,
        api_http_cap=480,semantic_cap=240,per_task_http=96,per_task_semantic=48,no_automatic_reruns=True,
        one_background_path=True,independent_confirmation=False,development_only=True,
        system_sha256=hashlib.sha256(core.SYSTEM.encode()).hexdigest(),legacy_merton_prompt_wording_retained=True)
    write(OUT/'registration.json',r);write(OUT/'api_precheck.json',dict(balance_available=available()))
    PACKAGE.mkdir();entries={}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
    publish=[ROOT/p for p in core.source_hashes()]+evidence+[OUT/'registration.json',OUT/'api_precheck.json']
    for i,p in enumerate(dict.fromkeys(publish)):
        raw=p.read_bytes();assert key not in raw;dest=PACKAGE/f'{i:03}.gz';dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
        entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),raw_sha256=hashlib.sha256(raw).hexdigest(),gzip_sha256=sha(dest))
    (PACKAGE/'manifest.json').write_bytes(json.dumps(dict(files=entries,credential_absent=True,lossless=True,weights_local_only=True),indent=2).encode())
    write(OUT/'publication.json',dict(files={p:v['gzip_sha256'] for p,v in entries.items()}));verify();print('TIMING_REGISTERED',len(entries),flush=True)
def verify():
    r=read(OUT/'registration.json')
    for p,h in r['files'].items():assert sha(p)==h,p
    assert core.source_hashes()==r['contracts']['11']['source_sha256']
    assert hashlib.sha256(core.SYSTEM.encode()).hexdigest()==r['system_sha256'];return r
def run():
    r=verify();revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote=subprocess.check_output(['git','-c','http.proxy=http://127.0.0.1:7890','ls-remote','origin','refs/heads/codex/llm-current-v2'],cwd=ROOT,text=True).split()[0];assert remote==revision
    for p,h in read(OUT/'publication.json')['files'].items():assert hashlib.sha256(subprocess.check_output(['git','cat-file','blob','HEAD:'+p],cwd=ROOT)).hexdigest()==h
    assert available(),'No available API balance'
    with (OUT/'started.lock').open('x') as f:f.write(str(os.getpid()))
    write(OUT/'launch.json',dict(pid=os.getpid(),started=time.time(),revision=revision));done=[];summary=[]
    try:
        for seed in r['seeds']:
            verify();calls=common.calls_under(OUT/'runs')
            assert len(calls)+96<=480 and sum(x.get('attempt')==1 for x in calls)+48<=240
            label=f'seed{seed}_three_positions';write(OUT/'progress.json',dict(status='running',task=label,completed=done,total_tasks=5,api_http_so_far=len(calls)))
            cmd=[sys.executable,'-u',str(HERE/'runner.py'),'--seed',str(seed),'--run-name',label,'--input-file',str(INPUT),'--training-directory',str(core.training(seed)),'--output-root',str(OUT/'runs'),'--phase','development']
            with (OUT/f'{label}.log').open('x',encoding='utf-8') as f:p=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
            assert p.returncode==0,f'{label}: preserve API/program failure'
            d=OUT/'runs'/label;auditor.audit(runner,d,read(INPUT),r['contracts'][str(seed)]['expected_parameter_sha256'])
            summary.extend(dict(e,seed=seed,offset=runner.OFFSETS[e['trace']]) for e in read(d/'episodes.json'));done.append(seed)
            verify();write(OUT/'summary.json',summary)
            calls=common.calls_under(OUT/'runs');assert len(calls)<=480 and sum(x.get('attempt')==1 for x in calls)<=240
        assert len(summary)==90
        comparison=[]
        for seed in r['seeds']:
            for trace,offset in enumerate(runner.OFFSETS):
                values={m:next(e['cost'] for e in summary if e['seed']==seed and e['trace']==trace and e['group']==m and e['scenario']=='shock') for m in runner.METHODS}
                comparison.append(dict(seed=seed,offset=offset,**values))
        write(OUT/'comparison.json',comparison)
        write(OUT/'completed.json',dict(episodes=90,rows=54000,seeds=done,api_http=len(calls),semantic=sum(x.get('attempt')==1 for x in calls)))
        write(OUT/'progress.json',dict(status='completed',completed=done,total_tasks=5,api_http=len(calls)))
    except Exception as e:
        write(OUT/'failed.json',dict(type=type(e).__name__,detail=str(e),completed=done,preserved=True,no_automatic_reruns=True))
        write(OUT/'progress.json',dict(status='stopped_for_diagnosis',completed=done,total_tasks=5));raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('register','run','verify'));a=p.parse_args();common.key_from_user();{'register':register,'run':run,'verify':verify}[a.action]()
