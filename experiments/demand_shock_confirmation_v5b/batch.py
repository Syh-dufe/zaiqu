"""Registered independent confirmation of frozen HAPPO and original online LLM."""
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
RUNNER=ROOT/'experiments/demand_shock_confirmation_v5/run_online.py'
LIBRARY=ROOT/'docs/artifacts/operator_discovery_v1/repaired_library.json'
REFERENCE=ROOT/'docs/artifacts/online_llm_development_v1/inputs.json'
PROTOCOL=ROOT/'docs/superpowers/plans/2026-10-05-independent-shock-confirmation-v5b.md'
OUTPUT=ROOT/'results/online_llm_shock_types/confirmation_v5b'
SEEDS=(11,12,13,14,15)
METHODS=('happo','online_feedback')
PROFILES=('single_surge','sustained_surge','double_surge','surge_then_drop')
CANDIDATE_SEEDS=tuple(range(20271402,20271452))
TIMING_OFFSETS=tuple(range(-10,10,2))
FIRST_PASS_HTTP_CAP=3200
FIRST_PASS_SEMANTIC_CAP=1600
TOTAL_HTTP_CAP=6400
TOTAL_SEMANTIC_CAP=3200
EXPECTED_HTTP=2000
EXPECTED_SEMANTIC=1000
PRIOR_DEVELOPMENT_HTTP=374
PRIOR_DEVELOPMENT_SEMANTIC=348
PRIOR_DEVELOPMENT_TOKENS=1369819
BOOTSTRAP_REPLICATES=20000
BOOTSTRAP_SEED=20271003

spec=importlib.util.spec_from_file_location('shock_confirmation_online_runner',RUNNER)
core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)
core.METHODS=METHODS
read,write,digest=core.read,core.write,core.digest


def training(seed):
    return ROOT/'results/learning_curve'/('curve_seed11_until_stable_v1' if seed==11 else f'curve_seed{seed}_formal_v1')


def intervals(profile,offset):
    if profile=='single_surge':return [(80+offset,100+offset,1.5)]
    if profile=='sustained_surge':return [(70+offset,120+offset,1.25)]
    if profile=='double_surge':return [(75+offset,95+offset,1.5),(115+offset,135+offset,1.5)]
    if profile=='surge_then_drop':return [(80+offset,100+offset,1.5),(100+offset,140+offset,.5)]
    raise ValueError(f'Unknown registered shock profile: {profile}')


def profile_trace(base,profile,offset):
    parts=[];shock=list(map(int,base))
    for start,end,factor in intervals(profile,offset):
        parts.append(dict(start=start,end=end,factor=factor))
        for index in range(start,end):
            scaled=factor*base[index]
            shock[index]=min(20,math.ceil(scaled)) if factor>1 else math.floor(scaled)
    event=dict(type=profile,start_index=min(x['start'] for x in parts),
        duration=max(x['end'] for x in parts)-min(x['start'] for x in parts),intervals=parts,
        timing_offset=offset,notification='single onset notification at first interval + 2 periods')
    return shock,event


def generated_batch(seed,batch):
    import numpy as np
    sys.path.insert(0,str(core.UPSTREAM))
    from envs.generator import merton
    np.random.seed(seed)
    bases=[list(map(int,merton(200,20).demand_list)) for _ in PROFILES]
    offset=TIMING_OFFSETS[batch]
    shocks=[];events=[]
    for base,profile in zip(bases,PROFILES):
        shock,event=profile_trace(base,profile,offset);shocks.append(shock);events.append(event)
    data=dict(demand_seed=seed,batch=batch+1,timing_offset=offset,base=bases,shock=shocks,events=events)
    core.validate_inputs(data)
    return data


def traces_in(value):
    found=[]
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('base','shock') and isinstance(item,list):
                found.extend(tuple(int(x) for x in trace[:200]) for trace in item
                    if isinstance(trace,list) and len(trace)>=200 and
                    all(type(x) in (int,float) and math.isfinite(x) for x in trace[:200]))
            else:found.extend(traces_in(item))
    elif isinstance(value,list):
        for item in value:found.extend(traces_in(item))
    return found


def historical_traces(exclude):
    used=set();sources=[]
    for parent in (ROOT/'results',ROOT/'docs/artifacts'):
        for path in parent.rglob('*.json'):
            if path.is_relative_to(exclude):continue
            try:data=read(path)
            except (ValueError,OSError):continue
            found=traces_in(data)
            if found:
                used.update(found);sources.append(dict(path=str(path.relative_to(ROOT)),sha256=digest(path),traces=len(found)))
    return used,sources


def trace_hash(trace):
    return hashlib.sha256(json.dumps(list(trace[:200]),separators=(',',':')).encode()).hexdigest()


def runtime_contract():
    import numpy as np
    import torch
    return dict(python_executable=sys.executable,python_version=sys.version,
        python_sha256=digest(Path(sys.executable)),numpy_version=np.__version__,torch_version=torch.__version__)


def input_path_records(data):
    return [(trace,scenario,tuple(data[scenario][trace][:200]))
            for trace in range(4) for scenario in ('base','shock')]


def register(out):
    if out.exists():raise RuntimeError('Refuse to overwrite an existing confirmation')
    if not os.environ.get('DEEPSEEK_API_KEY'):raise RuntimeError('DEEPSEEK_API_KEY unavailable; no registration started')
    out.mkdir(parents=True)
    source_hashes=core.source_hashes()
    training_contracts={str(seed):core.contracts(REFERENCE,LIBRARY,training(seed)) for seed in SEEDS}
    freeze=dict(phase='independent_confirmation',development_only=False,
        title='New-path independent confirmation of the original real-time LLM across four demand shock shapes',
        source_sha256=source_hashes,reference_input_sha256=digest(REFERENCE),library_sha256=digest(LIBRARY),
        protocol_sha256=digest(PROTOCOL),training_contracts=training_contracts,runtime=runtime_contract(),
        training_seeds=list(SEEDS),methods=list(METHODS),profiles=list(PROFILES),
        candidate_demand_seeds=list(CANDIDATE_SEEDS),timing_offsets=list(TIMING_OFFSETS),
        collision_screen='First ten candidate seed batches, in registered order, with all 200-period base/shock traces unseen and unique against historical traces and accepted paths; exact identity only; no outcome-based selection.',
        methods_frozen_before_input_generation=True,no_HAPPO_training=True,no_prompt_tuning=True,
        api_model=os.environ.get('DEEPSEEK_MODEL','deepseek-flash'),per_episode_http_cap=16,max_generation_events=4,
        planned_http_requests=EXPECTED_HTTP,planned_semantic_requests=EXPECTED_SEMANTIC,
        first_pass_http_ceiling=FIRST_PASS_HTTP_CAP,first_pass_semantic_ceiling=FIRST_PASS_SEMANTIC_CAP,
        max_http_requests_including_one_task_recovery=TOTAL_HTTP_CAP,
        max_semantic_requests_including_one_task_recovery=TOTAL_SEMANTIC_CAP,
        quota_recovery='At most one full rerun per task, only after HTTP 402 and a successful balance-availability check.',
        scenarios='Normal and registered shock counterpart for each exact same path; notification only in shock episodes.')
    write(out/'freeze.json',freeze)

    historical,historical_sources=historical_traces(out)
    accepted=[];accepted_paths=set();screen=[]
    for seed in CANDIDATE_SEEDS:
        if len(accepted)==10:break
        batch=len(accepted);data=generated_batch(seed,batch)
        local={};collisions=[];records=[]
        for trace,scenario,path in input_path_records(data):
            h=trace_hash(path);records.append(dict(trace=trace,scenario=scenario,sha256=h))
            if path in historical:collisions.append(dict(kind='historical_exact_path',trace=trace,scenario=scenario,sha256=h))
            if path in accepted_paths:collisions.append(dict(kind='accepted_path_duplicate',trace=trace,scenario=scenario,sha256=h))
            if path in local:
                previous=local[path]
                same_registered_pair=(previous['trace']==trace and {previous['scenario'],scenario}=={'base','shock'})
                if not same_registered_pair:
                    collisions.append(dict(kind='within_batch_duplicate',trace=trace,scenario=scenario,
                        duplicate_of=previous,sha256=h))
            else:local[path]=dict(trace=trace,scenario=scenario)
        record=dict(seed=seed,status='accepted' if not collisions else 'rejected_collision',
            batch=len(accepted)+1 if not collisions else None,path_hashes=records,collisions=collisions)
        screen.append(record)
        if collisions:continue
        accepted.append((seed,data));accepted_paths.update(path for _,_,path in input_path_records(data))
    if len(accepted)!=10:
        diagnosis=dict(status='insufficient_collision_free_batches',required=10,accepted=len(accepted),candidate_scan=screen,
            historical_source_manifest=historical_sources,no_rollout=True,no_API_calls=True)
        write(out/'collision_diagnosis.json',diagnosis)
        write(out/'registration_failed.json',dict(reason='Fewer than ten fixed candidate demand batches passed collision screen',inputs_preserved=True,no_rollout=True))
        raise RuntimeError('Collision screen could not produce the preregistered ten batches; do not append seeds ad hoc')
    write(out/'collision_diagnosis.json',dict(status='passed_exact_identity_screen',required=10,accepted=10,
        candidate_scan=screen,historical_source_manifest=historical_sources,
        historical_trace_count=len(historical),accepted_path_count=len(accepted_paths),
        path_definition='first 200 consumed integer demand values',selection_rule='registered seed order; collision only'))

    entries=[]
    for batch,(seed,data) in enumerate(accepted,1):
        path=out/'inputs'/f'batch{batch:02d}.json';path.parent.mkdir(parents=True,exist_ok=True);write(path,data)
        contracts={}
        for model_seed in SEEDS:
            value=core.contracts(path,LIBRARY,training(model_seed))
            expected=training_contracts[str(model_seed)]
            if {k:v for k,v in value.items() if k!='input_sha256'}!={k:v for k,v in expected.items() if k!='input_sha256'}:
                raise RuntimeError(f'Frozen contract differs for model seed {model_seed}')
            contracts[str(model_seed)]=value
        entries.append(dict(batch=batch,path=str(path),sha256=digest(path),demand_seed=seed,
            timing_offset=TIMING_OFFSETS[batch-1],profiles=list(PROFILES),contracts=contracts))
    manifest=dict(status='registered',phase='independent_confirmation',development_only=False,
        freeze_sha256=digest(out/'freeze.json'),collision_diagnosis_sha256=digest(out/'collision_diagnosis.json'),
        input_batches=entries,training_seeds=list(SEEDS),methods=list(METHODS),shock_types=list(PROFILES),
        independent_paths_per_type=10,distinct_type_paths=40,expected_episodes=800,expected_node_periods=480000,
        expected_rows=480000,expected_runs=50,planned_http_requests=EXPECTED_HTTP,
        planned_semantic_requests=EXPECTED_SEMANTIC,first_pass_http_ceiling=FIRST_PASS_HTTP_CAP,
        first_pass_semantic_ceiling=FIRST_PASS_SEMANTIC_CAP,total_http_ceiling=TOTAL_HTTP_CAP,
        total_semantic_ceiling=TOTAL_SEMANTIC_CAP,
        primary='Equal-weight pooled online_feedback minus HAPPO cost and downstream backlog on shocked episodes; both 95% crossed-bootstrap interval upper endpoints must be below zero for evidence of joint improvement.',
        secondary='By-type paired estimates and normal/shock difference-in-differences; descriptive, all cases retained.',
        bootstrap=dict(method='crossed resampling of five HAPPO model seeds and ten demand paths within each shock type',
            replicates=BOOTSTRAP_REPLICATES,seed=BOOTSTRAP_SEED,interval='percentile 95% two-sided'),
        no_test_feedback=True,no_random_candidate_method=True,no_training=True,fixed_all_cases_retained=True,
        prior_exposed_inputs_excluded=True,previous_development_resource_use=dict(http=PRIOR_DEVELOPMENT_HTTP,
            semantic=PRIOR_DEVELOPMENT_SEMANTIC,tokens=PRIOR_DEVELOPMENT_TOKENS))
    write(out/'manifest.json',manifest)
    return manifest


def verify_registration(out):
    freeze=read(out/'freeze.json');manifest=read(out/'manifest.json')
    assert digest(out/'freeze.json')==manifest['freeze_sha256']
    assert digest(out/'collision_diagnosis.json')==manifest['collision_diagnosis_sha256']
    assert core.source_hashes()==freeze['source_sha256']
    assert digest(LIBRARY)==freeze['library_sha256'] and digest(REFERENCE)==freeze['reference_input_sha256']
    assert digest(PROTOCOL)==freeze['protocol_sha256'] and runtime_contract()==freeze['runtime']
    assert len(manifest['input_batches'])==10
    for entry in manifest['input_batches']:
        path=Path(entry['path']);assert digest(path)==entry['sha256']
        data=read(path);core.validate_inputs(data)
        for seed in SEEDS:
            current=core.contracts(path,LIBRARY,training(seed))
            assert current==entry['contracts'][str(seed)]
            frozen=freeze['training_contracts'][str(seed)]
            assert {k:v for k,v in current.items() if k!='input_sha256'}=={k:v for k,v in frozen.items() if k!='input_sha256'}
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


def audit_child(directory,entry,seed):
    done=read(directory/'completed.json');episodes=read(directory/'episodes.json')
    assert done['episodes']==16 and done['rows']==9600 and done['training_updates']==0
    assert set(done['parameter_checks'])==set(METHODS)
    assert all(x['unchanged'] and x['before']==x['after'] for x in done['parameter_checks'].values())
    assert len(episodes)==16
    expected={(m,s,t) for m in METHODS for s in ('base','shock') for t in range(4)}
    assert {(x['group'],x['scenario'],x['trace']) for x in episodes}==expected
    for row in episodes:
        if row['group']=='happo' or row['scenario']=='base':assert row['episode_http']==0
        if row['scenario']=='shock':assert row['episode_http']<=16
    with (directory/'periods.csv').open(encoding='utf-8',newline='') as stream:rows=list(csv.DictReader(stream))
    assert len(rows)==9600
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
            llm=[tuple(r[k] for k in key) for r in rows if r['group']=='online_feedback' and r['scenario']==scenario and int(r['trace'])==trace and int(r['period'])<stop]
            assert ref==llm
    calls=read(directory/'calls.json')
    assert all(c.get('group')=='online_feedback' and c.get('scenario')=='shock' for c in calls)
    scores=read(directory/'scores.json')
    for trace in range(4):
        events=[r for r in scores if r.get('group')=='online_feedback' and r.get('trace')==trace and r.get('generation_event')]
        assert len(events)<=4
        assert all(len(r['candidates'])==4 and len(r['search_revision_feedback'])==4 for r in events)
    protocol=read(directory/'protocol.json')
    assert protocol.get('development_only') is False and protocol.get('independent_confirmation') is True
    assert done.get('independent_confirmation') is True and done.get('development_only') is False
    failures=read(directory/'runtime_failures.json')
    return dict(episodes=episodes,rows=rows,calls=calls,completed=done,runtime_failures=failures)


def crossed_bootstrap(values,replicates=BOOTSTRAP_REPLICATES,seed=BOOTSTRAP_SEED):
    import numpy as np
    # values[type] has shape [10 independent paths, 5 frozen models].
    rng=np.random.default_rng(seed);types=list(PROFILES);draws={t:np.empty(replicates) for t in types}
    overall=np.empty(replicates)
    for b in range(replicates):
        model_indices=rng.integers(0,5,size=5);per_type=[]
        for shock_type in types:
            path_indices=rng.integers(0,10,size=10)
            sample=values[shock_type][np.ix_(path_indices,model_indices)]
            draws[shock_type][b]=float(sample.mean());per_type.append(draws[shock_type][b])
        overall[b]=sum(per_type)/len(per_type)
    def summary(sample,point):
        low,high=np.quantile(sample,[.025,.975])
        return dict(mean=float(point),ci95_low=float(low),ci95_high=float(high),replicates=replicates)
    return dict(overall=summary(overall,sum(float(values[t].mean()) for t in types)/len(types)),
        by_type={t:summary(draws[t],float(values[t].mean())) for t in types})


def summarize(out,manifest,finished):
    episode_map={};rows=[];calls=[];runs=[]
    for task,item in finished.items():
        seed,batch=item['seed'],item['batch'];label=item['run_label'];entry=manifest['input_batches'][batch-1]
        audited=audit_child(out/'runs'/label,entry,seed)
        calls.extend(dict(seed=seed,batch=batch,**c) for c in audited['calls'])
        rows.extend(dict(seed=seed,batch=batch,shock_type=read(Path(entry['path']))['events'][int(r['trace'])]['type'],**r) for r in audited['rows'])
        runs.append(dict(seed=seed,batch=batch,run=label,log_sha256=digest(out/f'{label}.log'),input_sha256=entry['sha256'],
            episodes=16,api_requests=len(audited['calls']),node_periods=len(audited['rows']),
            runtime_failures=audited['runtime_failures'],completed_sha256=digest(out/'runs'/label/'completed.json')))
        for record in audited['episodes']:
            key=(seed,batch,record['group'],record['scenario'],record['trace'])
            episode_map[key]=dict(record,shock_type=read(Path(entry['path']))['events'][record['trace']]['type'])
    pairs=[];stratified={t:[] for t in PROFILES}
    for seed in SEEDS:
        for entry in manifest['input_batches']:
            batch=entry['batch'];data=read(Path(entry['path']))
            for trace,event in enumerate(data['events']):
                hs=episode_map[seed,batch,'happo','shock',trace];ls=episode_map[seed,batch,'online_feedback','shock',trace]
                hb=episode_map[seed,batch,'happo','base',trace];lb=episode_map[seed,batch,'online_feedback','base',trace]
                pair=dict(seed=seed,batch=batch,demand_seed=entry['demand_seed'],trace=trace,path_sha256=trace_hash(data['base'][trace]),
                    shock_type=event['type'],happo_shock_cost=hs['cost'],llm_shock_cost=ls['cost'],
                    shock_cost_delta=ls['cost']-hs['cost'],happo_shock_backlog=hs['downstream_backlog'],
                    llm_shock_backlog=ls['downstream_backlog'],shock_backlog_delta=ls['downstream_backlog']-hs['downstream_backlog'],
                    base_cost_delta=lb['cost']-hb['cost'],base_backlog_delta=lb['downstream_backlog']-hb['downstream_backlog'])
                pair['cost_difference_in_differences']=pair['shock_cost_delta']-pair['base_cost_delta']
                pair['backlog_difference_in_differences']=pair['shock_backlog_delta']-pair['base_backlog_delta']
                pairs.append(pair);stratified[event['type']].append(pair)
    def stat(items,key):
        vals=[float(x[key]) for x in items]
        return dict(n=len(vals),mean=sum(vals)/len(vals),better=sum(x<0 for x in vals),tied=sum(x==0 for x in vals),worse=sum(x>0 for x in vals))
    values={}
    for shock_type in PROFILES:
        items=stratified[shock_type]
        values[shock_type]={metric:__import__('numpy').array([[next(p for p in items if p['batch']==batch and p['seed']==seed)[key]
            for seed in SEEDS] for batch in range(1,11)],dtype=float)
            for metric,key in (('cost','shock_cost_delta'),('backlog','shock_backlog_delta'),
                               ('cost_difference_in_differences','cost_difference_in_differences'),
                               ('backlog_difference_in_differences','backlog_difference_in_differences'))}
    bootstrap={metric:crossed_bootstrap({t:values[t][metric] for t in PROFILES})
        for metric in ('cost','backlog','cost_difference_in_differences','backlog_difference_in_differences')}
    all_calls=all_recorded_calls(out);current_http=len(all_calls);current_semantic=sum(c.get('attempt')==1 for c in all_calls)
    if current_http>TOTAL_HTTP_CAP or current_semantic>TOTAL_SEMANTIC_CAP:
        raise RuntimeError('Registered full confirmation API ceiling exceeded; all outputs retained')
    usage=usage_totals(all_calls)
    prior=read(ROOT/'results/online_llm_shock_types/development_v4'/'summary.json')['all_attempt_token_usage']
    total_usage=dict(usage)
    for name,value in prior.items():
        if isinstance(value,(int,float)):total_usage[name]=total_usage.get(name,0)+value
    by_type={}
    actual=[]
    for shock_type in PROFILES:
        subset=stratified[shock_type]
        by_type[shock_type]=dict(cost=stat(subset,'shock_cost_delta'),backlog=stat(subset,'shock_backlog_delta'),
            cost_difference_in_differences=stat(subset,'cost_difference_in_differences'),
            backlog_difference_in_differences=stat(subset,'backlog_difference_in_differences'),
            bootstrap={metric:bootstrap[metric]['by_type'][shock_type] for metric in bootstrap})
    for entry in manifest['input_batches']:
        data=read(Path(entry['path']))
        for trace,event in enumerate(data['events']):
            parts=[]
            for part in event['intervals']:
                base=sum(data['base'][trace][part['start']:part['end']]);shock=sum(data['shock'][trace][part['start']:part['end']])
                parts.append(dict(start=part['start'],end=part['end'],factor=part['factor'],base_total=base,shock_total=shock,
                    actual_change_ratio=(shock-base)/base if base else None,
                    absolute_change=sum(abs(a-b) for a,b in zip(data['shock'][trace][part['start']:part['end']],data['base'][trace][part['start']:part['end']])),
                    clipped_periods=sum(part['factor']*x>20 for x in data['base'][trace][part['start']:part['end']]) if part['factor']>1 else 0))
            actual.append(dict(batch=entry['batch'],demand_seed=entry['demand_seed'],trace=trace,type=event['type'],
                timing_offset=event['timing_offset'],intervals=parts,
                unchanged_consumed_path=data['base'][trace][:200]==data['shock'][trace][:200]))
    primary_pass=all(bootstrap[m]['overall']['ci95_high']<0 for m in ('cost','backlog'))
    summary=dict(status='complete',phase='independent_confirmation',development_only=False,episodes=len(episode_map),
        expected_episodes=800,node_periods=len(rows),raw_node_period_rows=len(rows),models=len(SEEDS),
        paths_per_type=10,unique_type_paths=len(PROFILES)*10,paired_model_path_cases=len(pairs),
        overall=dict(cost=stat(pairs,'shock_cost_delta'),backlog=stat(pairs,'shock_backlog_delta'),
            cost_difference_in_differences=stat(pairs,'cost_difference_in_differences'),
            backlog_difference_in_differences=stat(pairs,'backlog_difference_in_differences'),
            crossed_bootstrap=bootstrap,co_primary_joint_improvement_supported=primary_pass),
        by_shock_type=by_type,paired_results=pairs,actual_profiles=actual,runs=runs,
        api_requests=current_http,semantic_requests=current_semantic,api_failures=sum(c.get('status')!='valid' for c in all_calls),
        api_failure_kinds={},token_usage=usage,project_cumulative_token_usage=total_usage,
        project_cumulative_http_requests=PRIOR_DEVELOPMENT_HTTP+current_http,
        project_cumulative_semantic_requests=PRIOR_DEVELOPMENT_SEMANTIC+current_semantic,
        prior_development_usage=dict(http=PRIOR_DEVELOPMENT_HTTP,semantic=PRIOR_DEVELOPMENT_SEMANTIC,tokens=PRIOR_DEVELOPMENT_TOKENS),
        api_seconds=sum(c.get('seconds',0) for c in all_calls),
        runtime_failures=[dict(seed=x['seed'],batch=x['batch'],failures=x['runtime_failures']) for x in runs if x.get('runtime_failures')],
        limits='Independent confirmation only if all 10 new paths per type pass exact historical collision checks; five HAPPO checkpoints remain the model sampling limitation.')
    for call in all_calls:
        kind=call.get('failure_kind','none')
        summary['api_failure_kinds'][kind]=summary['api_failure_kinds'].get(kind,0)+(call.get('status')!='valid')
    summary['api_failure_kinds']={k:v for k,v in summary['api_failure_kinds'].items() if v}
    write(out/'summary.json',summary)
    write(out/'completed.json',dict(status='completed',phase='independent_confirmation',episodes=len(episode_map),
        node_periods=len(rows),completed_runs=len(runs),api_requests=current_http,semantic_requests=current_semantic,
        summary_sha256=digest(out/'summary.json'),all_registered_cases_retained=True,training_updates=0))
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
    launch=dict(pid=os.getpid(),started=time.time(),manifest_sha256=digest(out/'manifest.json'),phase='independent_confirmation')
    with (out/'launch.json').open('x',encoding='utf-8') as stream:json.dump(launch,stream,indent=2)
    finished={};attempts=[];write(out/'progress.json',dict(status='running',completed_runs=[]))
    try:
        for seed in SEEDS:
            for entry in manifest['input_batches']:
                manifest=verify_registration(out);task=f'seed{seed}_batch{entry["batch"]:02d}';retry=0
                while True:
                    all_calls=all_recorded_calls(out)
                    current_http=len(all_calls);current_semantic=sum(c.get('attempt')==1 for c in all_calls)
                    if current_http+64>TOTAL_HTTP_CAP or current_semantic+32>TOTAL_SEMANTIC_CAP:
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
                if done.get('episodes')!=16 or done.get('rows')!=9600:raise RuntimeError(f'{task} incomplete child output')
                item=dict(seed=seed,batch=entry['batch'],run_label=label,episodes=16,node_periods=9600,
                    completed_sha256=digest(directory/'completed.json'),input_sha256=entry['sha256'],runtime_failures=done.get('runtime_failures',[]))
                finished[task]=item;write(out/'progress.json',dict(status='running',completed_runs=list(finished.values())))
                verify_registration(out)
        summary=summarize(out,manifest,finished)
        write(out/'progress.json',dict(status='completed',completed_runs=list(finished.values()),summary_sha256=digest(out/'summary.json')))
        print('INDEPENDENT_CONFIRMATION_COMPLETED',json.dumps(dict(overall=summary['overall'],by_type=summary['by_shock_type']),ensure_ascii=False),flush=True)
    except Exception as exc:
        write(out/'failed.json',dict(failure=type(exc).__name__,detail=str(exc)[:1000],completed_runs=list(finished.values()),
            raw_outputs_preserved=True,no_blind_restart=True))
        raise


if __name__=='__main__':main()
