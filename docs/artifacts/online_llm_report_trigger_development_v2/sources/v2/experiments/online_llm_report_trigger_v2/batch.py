"""Exposed-input development of report-triggered online LLM; frozen HAPPO."""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/'experiments/online_llm_report_trigger_v2/run.py'
LIBRARY=ROOT/'docs/artifacts/operator_discovery_v1/repaired_library.json'
REFERENCE=ROOT/'docs/artifacts/online_llm_development_v1/inputs.json'
PROTOCOL=ROOT/'docs/superpowers/plans/2026-10-05-online-report-trigger-development-v2.md'
OUTPUT=ROOT/'results/online_llm_report_trigger/development_v2'
SEEDS=(11,12,13,14,15)
METHODS=('happo','online_feedback','report_trigger_feedback')
PROFILES=('single_surge','sustained_surge','double_surge','surge_then_drop')
FIRST_PASS_HTTP_CAP=1280
FIRST_PASS_SEMANTIC_CAP=640
TOTAL_HTTP_CAP=2560
TOTAL_SEMANTIC_CAP=1280

spec=importlib.util.spec_from_file_location('shock_confirmation_online_runner',RUNNER)
core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)
core.METHODS=METHODS
read,write,digest=core.read,core.write,core.digest


def training(seed):
    return ROOT/'results/learning_curve'/('curve_seed11_until_stable_v1' if seed==11 else f'curve_seed{seed}_formal_v1')


def runtime_contract():
    import numpy as np
    import torch
    return dict(python_executable=sys.executable,python_version=sys.version,
        python_sha256=digest(Path(sys.executable)),numpy_version=np.__version__,torch_version=torch.__version__)


def register(out):
    if out.exists(): raise RuntimeError('Refuse overwrite')
    previous=ROOT/'results/online_llm_shock_types/confirmation_v5b'
    parent=read(previous/'manifest.json');done=read(previous/'completed.json')
    assert done['status']=='completed' and done['episodes']==800
    assert digest(previous/'summary.json')==done['summary_sha256']
    entries=[x for x in parent['input_batches'] if x['batch'] in (1,6)]
    assert len(entries)==2
    source=core.source_hashes()
    entries=[dict(x,contracts={str(seed):core.contracts(Path(x['path']),LIBRARY,training(seed)) for seed in SEEDS}) for x in entries]
    frozen=dict(phase='development',development_only=True,source_sha256=source,
        protocol_sha256=digest(PROTOCOL),spec_sha256=digest(ROOT/'docs/superpowers/specs/2026-10-05-online-report-trigger-design.md'),
        original_system_sha256=hashlib.sha256(core.SYSTEM.encode()).hexdigest(),
        input_role='v5b batch01 and06 exposed development; not new independent confirmation',
        parent_completed_sha256=digest(previous/'completed.json'),input_batches=entries,
        methods=list(METHODS),runtime=runtime_contract(),first_pass_http_cap=FIRST_PASS_HTTP_CAP,
        first_pass_semantic_cap=FIRST_PASS_SEMANTIC_CAP,total_http_cap=TOTAL_HTTP_CAP,total_semantic_cap=TOTAL_SEMANTIC_CAP,
        scheduling=dict(minimum_gap=20,maximum_wait=30,relative_report_change=.25,max_events=4),
        development_gate='both pooled cost and backlog strictly lower than current original; no type with both indicators higher')
    out.mkdir(parents=True);write(out/'freeze.json',frozen)
    manifest=dict(phase='development',development_only=True,input_batches=entries,training_seeds=list(SEEDS),methods=list(METHODS),
        freeze_sha256=digest(out/'freeze.json'),expected_episodes=240,expected_node_periods=144000,expected_runs=10,
        no_training=True,no_random_comparison=True,input_roles=frozen['input_role'])
    write(out/'manifest.json',manifest)
    return manifest


def verify_registration(out):
    frozen=read(out/'freeze.json');manifest=read(out/'manifest.json')
    assert digest(out/'freeze.json')==manifest['freeze_sha256']
    assert core.source_hashes()==frozen['source_sha256']
    assert digest(PROTOCOL)==frozen['protocol_sha256'] and runtime_contract()==frozen['runtime']
    assert hashlib.sha256(core.SYSTEM.encode()).hexdigest()==frozen['original_system_sha256']
    for entry in manifest['input_batches']:
        assert digest(Path(entry['path']))==entry['sha256']
        for seed in SEEDS:
            assert core.contracts(Path(entry['path']),LIBRARY,training(seed))==entry['contracts'][str(seed)]
    return manifest


def all_recorded_calls(out):
    records=[];root=out/'runs'
    if not root.exists():return records
    for path in root.rglob('calls.json'):
        try:records.extend(dict(run=path.parent.name,**item) for item in read(path))
        except (ValueError,OSError):continue
    return records


def usage_totals(records):
    usage={}
    for call in records:
        for name,value in (call.get('usage') or {}).items():
            if isinstance(value,(int,float)):usage[name]=usage.get(name,0)+value
    return usage


def fatal_http(directory):
    path=directory/'calls.json'
    if not path.exists():return None
    for record in read(path):
        if record.get('failure') in ('HTTP_401','HTTP_402','HTTP_403'):return record['failure']
    return None


def api_balance_available():
    key=os.environ.get('DEEPSEEK_API_KEY')
    if not key:raise RuntimeError('DeepSeek API credential is no longer available')
    request=urllib.request.Request('https://api.deepseek.com/user/balance',
        headers={'Authorization':'Bearer '+key,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:payload=json.loads(response.read().decode('utf-8'))
        return payload.get('is_available') is True
    except urllib.error.HTTPError as exc:
        if exc.code in (401,403):raise RuntimeError(f'Balance endpoint rejected credential HTTP_{exc.code}') from None
        return None
    except (urllib.error.URLError,TimeoutError,ValueError):return None


def wait_for_balance(out,task,retry):
    path=out/'quota_wait_history.json';history=read(path) if path.exists() else []
    while True:
        available=api_balance_available();checked=time.time()
        history.append(dict(task=task,retry=retry,checked_at=checked,balance_available=available));write(path,history)
        if available:
            write(out/'quota_wait.json',dict(status='available_retrying_once',task=task,retry=retry,checked_at=checked));return
        progress=read(out/'progress.json') if (out/'progress.json').exists() else {}
        write(out/'quota_wait.json',dict(status='waiting_for_balance',task=task,retry=retry,last_checked_at=checked))
        write(out/'progress.json',dict(status='waiting_for_balance',current_task=task,retry=retry,
            completed_runs=progress.get('completed_runs',[])))
        print('QUOTA_WAIT',task,'next_check_seconds=1800',flush=True);time.sleep(1800)


def audit_schedule(directory,scores,data):
    reports=read(directory/'delivered_reports.json')
    for trace in range(4):
        notification=data['events'][trace]['start_index']+2
        records=[r for r in scores if r['group']=='report_trigger_feedback' and r['scenario']=='shock' and r['trace']==trace]
        assert [r['decision_period']-1 for r in records]==list(range(notification,200,5))
        last=None;reference=None;last_delivered=-1;events=0
        for r in records:
            period=r['decision_period']-1
            visible=[v for v in reports if v['group']=='report_trigger_feedback' and v['scenario']=='shock'
                and v['trace']==trace and v['end_period']<=period]
            values=[v['demand_mean'] for v in visible[-2:]]
            mean=sum(values)/len(values) if values else 0.
            delivered=visible[-1]['end_period'] if visible else 0
            fresh=delivered>last_delivered
            gap=None if last is None else period-last
            change=None if reference is None else abs(mean-reference)/max(1.,abs(reference))
            trigger=fresh and events<4 and (events==0 or (gap>=20 and (change>=.25 or gap>=30)))
            d=r['generation_schedule']
            assert r['generation_event'] is trigger and d['trigger'] is trigger
            assert d['period']==period and d['events_before']==events and d['notification']==notification
            assert d['last_generation_period']==last and d['reference_mean']==reference
            assert math.isclose(d['report_mean'],mean,abs_tol=1e-12) and d['new_report']==fresh
            assert d['gap']==gap and d['relative_change']==change
            if trigger:events+=1;last=period;reference=mean;last_delivered=delivered
        assert events<=4


def audit_child(directory,entry,seed):
    done=read(directory/'completed.json');episodes=read(directory/'episodes.json')
    assert done['episodes']==24 and done['rows']==14400 and done['training_updates']==0
    assert set(done['parameter_checks'])==set(METHODS)
    assert all(x['unchanged'] and x['before']==x['after'] for x in done['parameter_checks'].values())
    assert len(episodes)==24
    expected={(m,s,t) for m in METHODS for s in ('base','shock') for t in range(4)}
    assert {(x['group'],x['scenario'],x['trace']) for x in episodes}==expected
    for row in episodes:
        if row['group']=='happo' or row['scenario']=='base':assert row['episode_http']==0
        if row['scenario']=='shock':assert row['episode_http']<=16
    with (directory/'periods.csv').open(encoding='utf-8',newline='') as stream:rows=list(csv.DictReader(stream))
    assert len(rows)==14400
    assert len({(r['group'],r['scenario'],r['trace'],r['period'],r['node']) for r in rows})==14400
    for episode in episodes:
        local=[r for r in rows if r['group']==episode['group'] and r['scenario']==episode['scenario'] and int(r['trace'])==episode['trace']]
        assert len(local)==600
        assert math.isclose(sum(float(r['cost']) for r in local)/600,episode['cost'],abs_tol=1e-9)
        assert math.isclose(sum(int(r['backlog']) for r in local if int(r['node'])==0)/200,episode['downstream_backlog'],abs_tol=1e-9)
    data=read(Path(entry['path']))
    for row in rows:
        assert math.isclose(float(row['cost']),int(row['inventory'])+int(row['backlog']),abs_tol=1e-9)
        assert 0<=int(row['actual_order'])<=20
        event=data['events'][int(row['trace'])]
        expected_notification=str(event['start_index']+3) if row['scenario']=='shock' and int(row['period'])>=event['start_index']+3 else ''
        assert row['notification_period']==expected_notification
    for trace,event in enumerate(data['events']):
        end=event['start_index']+3
        key=('period','node','cost','inventory','backlog','actual_order')
        for scenario in ('base','shock'):
            stop=201 if scenario=='base' else end
            ref=[tuple(r[k] for k in key) for r in rows if r['group']=='happo' and r['scenario']==scenario and int(r['trace'])==trace and int(r['period'])<stop]
            for group in METHODS[1:]:
                llm=[tuple(r[k] for k in key) for r in rows if r['group']==group and r['scenario']==scenario and int(r['trace'])==trace and int(r['period'])<stop]
                assert ref==llm
    calls=read(directory/'calls.json')
    assert all(c.get('group') in METHODS[1:] and c.get('scenario')=='shock' for c in calls)
    scores=read(directory/'scores.json')
    for trace in range(4):
        events=[r for r in scores if r.get('group') in METHODS[1:] and r.get('trace')==trace and r.get('generation_event')]
        assert all(sum(r['group']==g for r in events)<=4 for g in METHODS[1:])
        assert all(len(r['candidates'])==4 and len(r['search_revision_feedback'])==4 for r in events)
    audit_schedule(directory,scores,data)
    protocol=read(directory/'protocol.json')
    assert protocol.get('development_only') is True and protocol.get('independent_confirmation') is False
    assert done.get('independent_confirmation') is False and done.get('development_only') is True
    failures=read(directory/'runtime_failures.json')
    return dict(episodes=episodes,rows=rows,calls=calls,completed=done,runtime_failures=failures)


def summarize(out,manifest,finished):
    pairs=[];runs=[]
    for item in finished.values():
        entry=next(e for e in manifest['input_batches'] if e['batch']==item['batch'])
        audited=audit_child(out/'runs'/item['run_label'],entry,item['seed'])
        episodes=audited['episodes'];data=read(Path(entry['path']))
        for trace,event in enumerate(data['events']):
            selected={g:next(e for e in episodes if e['group']==g and e['scenario']=='shock' and e['trace']==trace) for g in METHODS}
            p=dict(seed=item['seed'],batch=item['batch'],trace=trace,type=event['type'],
                outcomes={g:dict(cost=e['cost'],backlog=e['downstream_backlog'],http=e['episode_http'],events=e['generation_events']) for g,e in selected.items()})
            p['cost_delta']=selected['report_trigger_feedback']['cost']-selected['online_feedback']['cost']
            p['backlog_delta']=selected['report_trigger_feedback']['downstream_backlog']-selected['online_feedback']['downstream_backlog']
            pairs.append(p)
        runs.append(item)
    assert len(pairs)==40 and len(runs)==10
    def stats(items):
        return {k:dict(mean=sum(p[k] for p in items)/len(items),better=sum(p[k]<0 for p in items),
            tied=sum(p[k]==0 for p in items),worse=sum(p[k]>0 for p in items)) for k in ('cost_delta','backlog_delta')}
    overall=stats(pairs);types={t:stats([p for p in pairs if p['type']==t]) for t in PROFILES}
    gate=all(overall[k]['mean']<0 for k in overall) and not any(all(v[k]['mean']>0 for k in v) for v in types.values())
    calls=all_recorded_calls(out);semantic=sum(c.get('attempt')==1 for c in calls)
    recovery=any('_quota_recovery' in c['run'] for c in calls)
    assert len(calls)<= (TOTAL_HTTP_CAP if recovery else FIRST_PASS_HTTP_CAP)
    assert semantic<= (TOTAL_SEMANTIC_CAP if recovery else FIRST_PASS_SEMANTIC_CAP)
    summary=dict(status='complete',development_only=True,independent_confirmation=False,episodes=240,node_periods=144000,
        paired_results=pairs,overall=overall,by_type=types,by_seed={str(seed):stats([p for p in pairs if p['seed']==seed]) for seed in SEEDS},
        development_gate_passed=gate,runs=runs,api_requests=len(calls),semantic_requests=semantic,token_usage=usage_totals(calls),
        api_failures=sum(c.get('status')!='valid' for c in calls),API_nondeterminism_limitation=True,no_test_generalization_claim=True)
    write(out/'summary.json',summary)
    write(out/'completed.json',dict(status='completed',development_only=True,episodes=240,node_periods=144000,
        completed_runs=10,summary_sha256=digest(out/'summary.json'),training_updates=0))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--register-only',action='store_true');parser.add_argument('--preflight',action='store_true');parser.add_argument('--run',action='store_true')
    options=parser.parse_args()
    if sum((options.register_only,options.preflight,options.run))!=1:parser.error('Choose exactly one experiment phase')
    out=OUTPUT
    if options.register_only:
        try:manifest=register(out)
        except Exception as exc:
            if out.exists() and not (out/'registration_failed.json').exists():
                write(out/'registration_failed.json',dict(failure=type(exc).__name__,detail=str(exc)[:1000],inputs_preserved=True,no_rollout=True))
            raise
        print('REGISTERED',manifest['expected_episodes'],manifest['expected_node_periods'],flush=True);return
    manifest=verify_registration(out)
    if options.preflight:
        if not os.environ.get('DEEPSEEK_API_KEY'):raise RuntimeError('Key unavailable for no-API contract preflight')
        checks=[]
        for entry in manifest['input_batches']:
            for seed in SEEDS:
                command=[sys.executable,str(RUNNER),'--run-name',f'preflight_seed{seed}_batch{entry["batch"]:02d}',
                    '--input-file',entry['path'],'--training-directory',str(training(seed)),'--operator-library',str(LIBRARY),
                    '--output-root',str(out/'preflight'),'--preflight']
                result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,check=True)
                checks.append(dict(seed=seed,batch=entry['batch'],contract=json.loads(result.stdout)))
        write(out/'preflight.json',dict(status='passed_no_api_or_rollout',checks=checks,freeze_sha256=digest(out/'freeze.json')))
        print('PREFLIGHT_PASSED checks=',len(checks),'API_calls=0',flush=True);return
    if not os.environ.get('DEEPSEEK_API_KEY'):raise RuntimeError('API key unavailable; no rollout started')
    if any((out/name).exists() for name in ('launch.json','failed.json','completed.json')):raise RuntimeError('Already launched or finished; refuse repeat')
    if not (out/'preflight.json').exists() or read(out/'preflight.json').get('status')!='passed_no_api_or_rollout':
        raise RuntimeError('No successful no-API preflight')
    launch=dict(pid=os.getpid(),started=time.time(),manifest_sha256=digest(out/'manifest.json'),phase='development')
    with (out/'launch.json').open('x',encoding='utf-8') as stream:json.dump(launch,stream,indent=2)
    finished={};attempts=[];write(out/'progress.json',dict(status='running',completed_runs=[]))
    try:
        for seed in SEEDS:
            for entry in manifest['input_batches']:
                manifest=verify_registration(out);task=f'seed{seed}_batch{entry["batch"]:02d}';retry=0
                while True:
                    all_calls=all_recorded_calls(out)
                    current_http=len(all_calls);current_semantic=sum(c.get('attempt')==1 for c in all_calls)
                    http_cap=TOTAL_HTTP_CAP if attempts else FIRST_PASS_HTTP_CAP
                    semantic_cap=TOTAL_SEMANTIC_CAP if attempts else FIRST_PASS_SEMANTIC_CAP
                    if current_http+128>http_cap or current_semantic+64>semantic_cap:
                        raise RuntimeError('Insufficient registered API budget for the next complete task')
                    label=task if retry==0 else f'{task}_quota_recovery{retry}'
                    command=[sys.executable,'-u',str(RUNNER),'--run-name',label,'--input-file',entry['path'],
                        '--training-directory',str(training(seed)),'--operator-library',str(LIBRARY),'--output-root',str(out/'runs')]
                    write(out/'progress.json',dict(status='running',current_task=task,attempt=retry+1,completed_runs=list(finished.values())))
                    with (out/f'{label}.log').open('x',encoding='utf-8') as stream:proc=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
                    directory=out/'runs'/label
                    if proc.returncode==0:break
                    fatal=fatal_http(directory)
                    attempts.append(dict(task=task,run_label=label,exit_code=proc.returncode,fatal_http=fatal,
                        log_sha256=digest(out/f'{label}.log'),http_requests=len(read(directory/'calls.json')) if (directory/'calls.json').exists() else 0))
                    write(out/'attempts.json',attempts)
                    if fatal=='HTTP_402' and retry==0:wait_for_balance(out,task,1);retry=1;continue
                    raise RuntimeError(f'{task} failed with {fatal or "non-quota process/audit error"}; preserve raw output')
                done=read(directory/'completed.json')
                if done.get('episodes')!=24 or done.get('rows')!=14400:raise RuntimeError(f'{task} incomplete child output')
                item=dict(seed=seed,batch=entry['batch'],run_label=label,episodes=24,node_periods=14400,
                    completed_sha256=digest(directory/'completed.json'),input_sha256=entry['sha256'],runtime_failures=done.get('runtime_failures',[]))
                finished[task]=item;write(out/'progress.json',dict(status='running',completed_runs=list(finished.values())))
                verify_registration(out)
        summary=summarize(out,manifest,finished)
        write(out/'progress.json',dict(status='completed',completed_runs=list(finished.values()),summary_sha256=digest(out/'summary.json')))
        print('INDEPENDENT_CONFIRMATION_COMPLETED',json.dumps(dict(overall=summary['overall'],by_type=summary['by_type']),ensure_ascii=False),flush=True)
    except Exception as exc:
        write(out/'failed.json',dict(failure=type(exc).__name__,detail=str(exc)[:1000],completed_runs=list(finished.values()),
            raw_outputs_preserved=True,no_blind_restart=True))
        raise


if __name__=='__main__':main()
