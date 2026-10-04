"""Registered development replay of the frozen original LLM shock-shape study."""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/'experiments/demand_shock_types_v4/run_online.py'
REFERENCE=ROOT/'docs/artifacts/online_llm_development_v1/inputs.json'
LIBRARY=ROOT/'docs/artifacts/operator_discovery_v1/repaired_library.json'
PROTOCOL=ROOT/'docs/superpowers/plans/2026-10-05-unseen-shock-types-repair-v4.md'
REPLAY_ROOT=ROOT/'results/online_llm_shock_types/development_v3'
SEEDS=(11,12,13,14,15)
METHODS=('happo','online_feedback')
PROFILES=(
    'single_surge','sustained_surge','double_surge','surge_then_drop')
DEMAND_SEEDS=(20271201,20271202)
TIMINGS=(
    {'single_surge':[(80,100,1.5)],'sustained_surge':[(70,120,1.25)],
     'double_surge':[(65,85,1.5),(105,125,1.5)],'surge_then_drop':[(80,100,1.5),(100,140,0.5)]},
    {'single_surge':[(90,110,1.5)],'sustained_surge':[(80,130,1.25)],
     'double_surge':[(70,90,1.5),(110,130,1.5)],'surge_then_drop':[(90,110,1.5),(110,150,0.5)]})

spec=importlib.util.spec_from_file_location('shock_types_online_runner',RUNNER)
core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)
core.METHODS=METHODS
read,write,digest=core.read,core.write,core.digest


def training(seed):
    return core.training(seed)


def profile_trace(base,profile,batch):
    intervals=[]
    for start,end,factor in TIMINGS[batch][profile]:
        intervals.append(dict(start=start,end=end,factor=factor))
    shock=list(map(int,base))
    for interval in intervals:
        for index in range(interval['start'],interval['end']):
            scaled=interval['factor']*base[index]
            shock[index]=min(20,math.ceil(scaled)) if interval['factor']>1 else math.floor(scaled)
    event=dict(type=profile,start_index=min(x['start'] for x in intervals),
        duration=max(x['end'] for x in intervals)-min(x['start'] for x in intervals),
        intervals=intervals,notification='single onset notification at first interval')
    return shock,event


def generate_inputs():
    import numpy as np
    sys.path.insert(0,str(core.UPSTREAM))
    from envs.generator import merton
    values=[]
    for batch,seed in enumerate(DEMAND_SEEDS):
        np.random.seed(seed)
        bases=[list(map(int,merton(200,20).demand_list)) for _ in range(4)]
        shocks=[];events=[]
        for base,profile in zip(bases,PROFILES):
            shock,event=profile_trace(base,profile,batch)
            shocks.append(shock);events.append(event)
        data=dict(demand_seed=seed,batch=batch+1,base=bases,shock=shocks,events=events)
        core.validate_inputs(data)
        values.append(data)
    return values


def traces_in(value):
    found=[]
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('base','shock') and isinstance(item,list):
                found.extend(tuple(int(x) for x in trace[:200]) for trace in item
                    if isinstance(trace,list) and len(trace)>=200 and
                    all(type(x) in (int,float) and math.isfinite(x) for x in trace[:200]))
            else:
                found.extend(traces_in(item))
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
            traces=traces_in(data)
            if traces:
                used.update(traces);sources.append(dict(path=str(path.relative_to(ROOT)),sha256=digest(path),traces=len(traces)))
    return used,sources


def frozen_model_contracts():
    contracts={}
    for seed in SEEDS:
        contracts[str(seed)]=core.contracts(REFERENCE,LIBRARY,training(seed))
    return contracts


def runtime_contract():
    import numpy as np
    import torch
    return dict(python_executable=sys.executable,python_version=sys.version,
        python_sha256=digest(Path(sys.executable)),numpy_version=np.__version__,torch_version=torch.__version__)


def register(out):
    if out.exists():raise RuntimeError('Refuse to overwrite an existing experiment')
    if not os.environ.get('DEEPSEEK_API_KEY'):raise RuntimeError('DEEPSEEK_API_KEY is unavailable in this process')
    out.mkdir(parents=True)
    sources=core.source_hashes()
    contract=frozen_model_contracts()
    freeze=dict(phase='development',development_only=True,
        title='Development replay of the four registered shock shapes after a v3 post-run audit defect',
        source_sha256=sources,reference_input_sha256=digest(REFERENCE),
        library_sha256=digest(LIBRARY),protocol_sha256=digest(PROTOCOL),model_contracts=contract,
        runtime=runtime_contract(),
        training_seeds=list(SEEDS),methods=list(METHODS),
        demand_generator='Exact byte-for-byte replay of the two frozen v3 input batches; no new demand generation',
        demand_seeds=list(DEMAND_SEEDS),profiles=list(PROFILES),timing_profiles=TIMINGS,
        transformation='surge: min(20,ceil(factor*d)); drop: floor(factor*d); all other periods unchanged',
        methods_frozen_before_replay=True,prior_input_exposure_acknowledged=True,training_updates=0,
        no_prompt_tuning_on_registered_cases=True,api_model=os.environ.get('DEEPSEEK_MODEL','deepseek-flash'),
        per_episode_http_cap=16,planned_http_cap=640,planned_semantic_cap=320,
        prior_failed_attempt_http=37,prior_failed_attempt_semantic=31,
        cumulative_maximum_http_cap=1317,cumulative_maximum_semantic_cap=671,
        maximum_http_cap=1280,maximum_semantic_cap=640,max_recovery_attempts_per_task=1,
        scenario_note='Only first onset is notified; double_surge has no second notification. Event fields are hidden from prompts.')
    write(out/'freeze.json',freeze)
    prior_manifest=read(REPLAY_ROOT/'manifest.json')
    if prior_manifest.get('status')!='registered' or prior_manifest.get('development_only') is not True:
        raise RuntimeError('The v3 failed-attempt input registration is unavailable')
    prior_freeze=read(REPLAY_ROOT/'freeze.json')
    if digest(REPLAY_ROOT/'freeze.json')!=prior_manifest.get('freeze_sha256'):
        raise RuntimeError('The v3 freeze record changed; replay provenance cannot be verified')
    for relative,expected_hash in prior_freeze['source_sha256'].items():
        if digest(ROOT/relative)!=expected_hash:
            raise RuntimeError(f'A frozen v3 source changed: {relative}')
    generated=[]
    for old_entry in prior_manifest['input_batches']:
        source=Path(old_entry['path'])
        if digest(source)!=old_entry['sha256']:
            raise RuntimeError('A prior fixed input changed; do not replay altered data')
        data=read(source);core.validate_inputs(data);generated.append(data)
    replay_diagnosis=read(REPLAY_ROOT/'collision_diagnosis.json')
    if replay_diagnosis.get('historical_collisions') or replay_diagnosis.get('cross_path_collisions') or replay_diagnosis.get('duplicate_base') or replay_diagnosis.get('duplicate_shock'):
        raise RuntimeError('The original collision audit was not clean; do not replay')
    new_base=[];new_shock=[]
    for batch,data in enumerate(generated,1):
        path=out/'inputs'/f'batch{batch}.json';path.parent.mkdir(parents=True,exist_ok=True)
        old_entry=prior_manifest['input_batches'][batch-1]
        if data['demand_seed']!=old_entry['demand_seed']:
            raise RuntimeError('Prior input batch order changed')
        shutil.copyfile(old_entry['path'],path)
        if digest(path)!=old_entry['sha256']:
            raise RuntimeError('Copied replay input hash differs from failed v3 registration')
        for trace,profile in enumerate(PROFILES):
            base=tuple(data['base'][trace][:200]);shock=tuple(data['shock'][trace][:200])
            new_base.append((batch,trace,base));new_shock.append((batch,trace,shock))
    cross=[]
    for i,(batch,trace,shock) in enumerate(new_shock):
        for other_batch,other_trace,base in new_base:
            if (batch,trace)!=(other_batch,other_trace) and shock==base:
                cross.append(dict(shock=[batch,trace],base=[other_batch,other_trace]))
    duplicate_base=len({x[2] for x in new_base})!=len(new_base)
    duplicate_shock=len({x[2] for x in new_shock})!=len(new_shock)
    write(out/'collision_diagnosis.json',dict(historical_collisions='not_applicable_replay_of_exposed_development_inputs',
        cross_path_collisions=cross,duplicate_base=duplicate_base,duplicate_shock=duplicate_shock,
        unchanged_shock_paths=[dict(batch=b,trace=t,profile=PROFILES[t]) for (b,t,s),(_,_,q) in zip(new_base,new_shock) if s==q],
        prior_v3_manifest_sha256=digest(REPLAY_ROOT/'manifest.json'),
        prior_v3_collision_diagnosis_sha256=digest(REPLAY_ROOT/'collision_diagnosis.json'),
        prior_v3_attempt_diagnosis_sha256=digest(REPLAY_ROOT/'diagnosis.json'),
        source_input_sha256=[x['sha256'] for x in prior_manifest['input_batches']],
        prior_v3_http_requests=37,prior_v3_semantic_attempts=31,
        inputs_are_unseen=False,development_replay=True,no_resampling=True))
    if cross or duplicate_base or duplicate_shock:
        write(out/'registration_failed.json',dict(reason='Replay input integrity or internal collision failure; inputs preserved',
            collision_diagnosis_sha256=digest(out/'collision_diagnosis.json')))
        raise RuntimeError('Fixed replay input integrity check failed; preserve all evidence')
    entries=[]
    reference_contract=contract
    for batch,data in enumerate(generated,1):
        path=out/'inputs'/f'batch{batch}.json'
        seed_contracts={}
        for seed in SEEDS:
            candidate=core.contracts(path,LIBRARY,training(seed))
            reference_item=reference_contract[str(seed)]
            if {k:v for k,v in candidate.items() if k!='input_sha256'}!={k:v for k,v in reference_item.items() if k!='input_sha256'}:
                raise RuntimeError(f'Frozen model contract changed for seed {seed}')
            seed_contracts[str(seed)]=candidate
        entries.append(dict(batch=batch,path=str(path),sha256=digest(path),demand_seed=data['demand_seed'],
            profiles=PROFILES,contracts=seed_contracts))
    manifest=dict(status='registered',phase='development',development_only=True,
        freeze_sha256=digest(out/'freeze.json'),input_batches=entries,training_seeds=list(SEEDS),
        methods=list(METHODS),shock_types=list(PROFILES),replicates_per_type=2,
        expected_episodes=160,expected_node_periods=96000,expected_rows=96000,
        planned_http_requests=640,planned_semantic_requests=320,
        maximum_http_requests=1280,maximum_semantic_requests=640,
        cumulative_maximum_http_requests=1317,cumulative_maximum_semantic_requests=671,
        primary='online_feedback minus HAPPO on shocked episodes, descriptive development estimate',
        secondary='difference-in-differences: (feedback shock-base)-(HAPPO shock-base), by shock type',
        no_test_feedback=True,no_random_candidate_method=True,no_training=True,
        fixed_all_cases_retained=True,prior_input_sources=[str(REPLAY_ROOT/'manifest.json')],
        input_status='Previously exposed development inputs replayed after code-only audit repair',
        unseen_test=False,prior_failed_v3_http_requests=37,prior_failed_v3_semantic_attempts=31)
    write(out/'manifest.json',manifest)
    return manifest


def verify_registration(out):
    freeze=read(out/'freeze.json');manifest=read(out/'manifest.json')
    assert digest(out/'freeze.json')==manifest['freeze_sha256']
    assert core.source_hashes()==freeze['source_sha256']
    assert digest(LIBRARY)==freeze['library_sha256'] and digest(REFERENCE)==freeze['reference_input_sha256']
    assert digest(PROTOCOL)==freeze['protocol_sha256']
    assert runtime_contract()==freeze['runtime']
    for seed in SEEDS:
        base=freeze['model_contracts'][str(seed)]
        for entry in manifest['input_batches']:
            p=Path(entry['path']);assert digest(p)==entry['sha256']
            data=read(p);core.validate_inputs(data)
            current=core.contracts(p,LIBRARY,training(seed))
            assert current==entry['contracts'][str(seed)]
            assert {k:v for k,v in current.items() if k!='input_sha256'}=={k:v for k,v in base.items() if k!='input_sha256'}
    return manifest


def all_recorded_calls(out):
    records=[];root=out/'runs'
    if not root.exists():return records
    for path in root.rglob('calls.json'):
        try:
            label=path.parent.name
            records.extend(dict(run=label,**item) for item in read(path))
        except (ValueError,OSError):continue
    return records


def fatal_http(directory):
    path=directory/'calls.json'
    if not path.exists():return None
    for record in read(path):
        if record.get('failure') in ('HTTP_401','HTTP_402','HTTP_403'):
            return record['failure']
    return None


def api_balance_available():
    key=os.environ.get('DEEPSEEK_API_KEY')
    if not key:raise RuntimeError('DeepSeek API credential is no longer available')
    request=urllib.request.Request('https://api.deepseek.com/user/balance',
        headers={'Authorization':'Bearer '+key,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            payload=json.loads(response.read().decode('utf-8'))
        return payload.get('is_available') is True
    except urllib.error.HTTPError as exc:
        if exc.code in (401,403):raise RuntimeError(f'Balance endpoint rejected credential HTTP_{exc.code}') from None
        return None
    except (urllib.error.URLError,TimeoutError,ValueError):
        return None


def wait_for_balance(out,task,retry):
    history_path=out/'quota_wait_history.json'
    history=read(history_path) if history_path.exists() else []
    while True:
        available=api_balance_available();checked=time.time()
        history.append(dict(task=task,retry=retry,checked_at=checked,balance_available=available))
        write(history_path,history)
        if available:
            write(out/'quota_wait.json',dict(status='available_retrying_once',task=task,retry=retry,checked_at=checked))
            return
        write(out/'quota_wait.json',dict(status='waiting_for_balance',task=task,retry=retry,last_checked_at=checked))
        progress=read(out/'progress.json') if (out/'progress.json').exists() else {}
        write(out/'progress.json',dict(status='waiting_for_balance',current_task=task,retry=retry,
            completed_runs=progress.get('completed_runs',[])))
        print('QUOTA_WAIT',task,'next_check_seconds=1800',flush=True)
        time.sleep(1800)


def audit_child(directory,entry,seed):
    done=read(directory/'completed.json');episodes=read(directory/'episodes.json')
    assert done['episodes']==16 and done['rows']==9600 and done['training_updates']==0
    assert set(done['parameter_checks'])==set(METHODS)
    assert all(item['unchanged'] and item['before']==item['after'] for item in done['parameter_checks'].values())
    assert len(episodes)==16
    expected={(m,s,t) for m in METHODS for s in ('base','shock') for t in range(4)}
    assert {(x['group'],x['scenario'],x['trace']) for x in episodes}==expected
    for row in episodes:
        if row['group']=='happo' or row['scenario']=='base':assert row['episode_http']==0
        if row['scenario']=='shock':assert row['episode_http']<=16
    with (directory/'periods.csv').open(encoding='utf-8',newline='') as stream:rows=list(csv.DictReader(stream))
    assert len(rows)==9600
    for row in rows:
        assert math.isclose(float(row['cost']),int(row['inventory'])+int(row['backlog']),abs_tol=1e-9)
        assert 0<=int(row['actual_order'])<=20
    for trace,event in enumerate(read(Path(entry['path']))['events']):
        end=event['start_index']+3
        key=('period','node','cost','inventory','backlog','actual_order')
        for scenario in ('base','shock'):
            stop=201 if scenario=='base' else end
            ref=[tuple(r[k] for k in key) for r in rows if r['group']=='happo' and r['scenario']==scenario and int(r['trace'])==trace and int(r['period'])<stop]
            llm=[tuple(r[k] for k in key) for r in rows if r['group']=='online_feedback' and r['scenario']==scenario and int(r['trace'])==trace and int(r['period'])<stop]
            assert ref==llm
    calls=read(directory/'calls.json')
    assert all(c['group']=='online_feedback' and c['scenario']=='shock' for c in calls)
    return dict(episodes=episodes,rows=rows,calls=calls,completed=done)


def summarize(out,manifest,finished):
    episode_map={};rows=[];calls=[];runs=[]
    for task,item in finished.items():
        seed,batch=item['seed'],item['batch'];label=item['run_label']
        entry=manifest['input_batches'][batch-1];data=read(Path(entry['path']))
        directory=out/'runs'/label;audited=audit_child(directory,entry,seed)
        calls.extend(dict(seed=seed,batch=batch,**c) for c in audited['calls'])
        rows.extend(dict(seed=seed,batch=batch,shock_type=data['events'][int(r['trace'])]['type'],**r) for r in audited['rows'])
        runs.append(dict(seed=seed,batch=batch,run=label,log_sha256=digest(out/f'{label}.log'),
                         input_sha256=entry['sha256'],episodes=16,api_requests=len(audited['calls']),
                         node_periods=len(audited['rows'])))
        for record in audited['episodes']:
            key=(seed,batch,record['group'],record['scenario'],record['trace'])
            episode_map[key]=dict(record,shock_type=data['events'][record['trace']]['type'])
    pairs=[];stratified={}
    for seed in SEEDS:
        for entry in manifest['input_batches']:
            batch=entry['batch'];data=read(Path(entry['path']))
            for trace,event in enumerate(data['events']):
                happo_shock=episode_map[seed,batch,'happo','shock',trace]
                llm_shock=episode_map[seed,batch,'online_feedback','shock',trace]
                happo_base=episode_map[seed,batch,'happo','base',trace]
                llm_base=episode_map[seed,batch,'online_feedback','base',trace]
                pair=dict(seed=seed,batch=batch,trace=trace,shock_type=event['type'],
                    happo_shock_cost=happo_shock['cost'],llm_shock_cost=llm_shock['cost'],
                    shock_cost_delta=llm_shock['cost']-happo_shock['cost'],
                    happo_shock_backlog=happo_shock['downstream_backlog'],
                    llm_shock_backlog=llm_shock['downstream_backlog'],
                    shock_backlog_delta=llm_shock['downstream_backlog']-happo_shock['downstream_backlog'],
                    base_cost_delta=llm_base['cost']-happo_base['cost'],
                    base_backlog_delta=llm_base['downstream_backlog']-happo_base['downstream_backlog'])
                pair['cost_difference_in_differences']=pair['shock_cost_delta']-pair['base_cost_delta']
                pair['backlog_difference_in_differences']=pair['shock_backlog_delta']-pair['base_backlog_delta']
                pairs.append(pair);stratified.setdefault(event['type'],[]).append(pair)
    def metric(items,key):return sum(x[key] for x in items)/len(items) if items else None
    by_type={name:dict(n=len(items),mean_shock_cost_delta=metric(items,'shock_cost_delta'),
        mean_shock_backlog_delta=metric(items,'shock_backlog_delta'),
        mean_cost_difference_in_differences=metric(items,'cost_difference_in_differences'),
        mean_backlog_difference_in_differences=metric(items,'backlog_difference_in_differences'),
        cost_pairs_better=sum(x['shock_cost_delta']<0 for x in items),cost_pairs_tied=sum(x['shock_cost_delta']==0 for x in items),
        cost_pairs_worse=sum(x['shock_cost_delta']>0 for x in items),
        backlog_pairs_better=sum(x['shock_backlog_delta']<0 for x in items),backlog_pairs_tied=sum(x['shock_backlog_delta']==0 for x in items),
        backlog_pairs_worse=sum(x['shock_backlog_delta']>0 for x in items)) for name,items in stratified.items()}
    overall=dict(n=len(pairs),mean_shock_cost_delta=metric(pairs,'shock_cost_delta'),
        mean_shock_backlog_delta=metric(pairs,'shock_backlog_delta'),
        mean_cost_difference_in_differences=metric(pairs,'cost_difference_in_differences'),
        mean_backlog_difference_in_differences=metric(pairs,'backlog_difference_in_differences'),
        cost_pairs_better=sum(x['shock_cost_delta']<0 for x in pairs),cost_pairs_tied=sum(x['shock_cost_delta']==0 for x in pairs),
        cost_pairs_worse=sum(x['shock_cost_delta']>0 for x in pairs),
        backlog_pairs_better=sum(x['shock_backlog_delta']<0 for x in pairs),backlog_pairs_tied=sum(x['shock_backlog_delta']==0 for x in pairs),
        backlog_pairs_worse=sum(x['shock_backlog_delta']>0 for x in pairs))
    usage={};prior_usage={}
    all_calls=all_recorded_calls(out)
    prior_calls=read(REPLAY_ROOT/'runs'/'seed11_batch1'/'calls.json')
    for call in all_calls:
        for name,value in (call.get('usage') or {}).items():
            if isinstance(value,(int,float)):usage[name]=usage.get(name,0)+value
    for call in prior_calls:
        for name,value in (call.get('usage') or {}).items():
            if isinstance(value,(int,float)):prior_usage[name]=prior_usage.get(name,0)+value
    prior_http=len(prior_calls);prior_semantic=sum(c.get('attempt')==1 for c in prior_calls)
    if len(all_calls)>manifest['maximum_http_requests'] or sum(c.get('attempt')==1 for c in all_calls)>manifest['maximum_semantic_requests']:
        raise RuntimeError('Registered remaining API hard budget exceeded; preserve all outputs')
    if len(all_calls)+prior_http>manifest['cumulative_maximum_http_requests'] or sum(c.get('attempt')==1 for c in all_calls)+prior_semantic>manifest['cumulative_maximum_semantic_requests']:
        raise RuntimeError('Cumulative v3 failed-attempt plus v4 API hard budget exceeded; preserve all outputs')
    all_usage=dict(usage)
    for name,value in prior_usage.items():all_usage[name]=all_usage.get(name,0)+value
    summary=dict(status='complete',phase='development_only',episodes=len(episode_map),
        expected_episodes=160,node_periods=len(rows),
        raw_node_period_rows=len(rows),models=len(SEEDS),shock_pairs=len(pairs),overall=overall,by_shock_type=by_type,
        paired_results=pairs,runs=runs,api_requests=len(calls),all_attempt_http_requests=len(all_calls)+prior_http,
        current_replay_attempt_http_requests=len(all_calls),prior_failed_attempt_http_requests=prior_http,
        all_attempt_semantic_requests=sum(c.get('attempt')==1 for c in all_calls)+prior_semantic,
        api_failures=sum(c.get('status')!='valid' for c in all_calls),
        prior_failed_v3_attempt=dict(http_requests=prior_http,semantic_attempts=prior_semantic,
            valid_responses=sum(c.get('status')=='valid' for c in prior_calls),
            failed_responses=sum(c.get('status')!='valid' for c in prior_calls),
            token_usage=prior_usage,included_in_outcome_estimates=False),
        token_usage=usage,all_attempt_token_usage=all_usage,
        api_seconds=sum(c.get('seconds',0) for c in all_calls),
        runtime_failures=[dict(task=task,run=item['run_label'],failures=item.get('runtime_failures',[]))
                          for task,item in finished.items() if item.get('runtime_failures')],
        actual_profiles=[])
    for entry in manifest['input_batches']:
        data=read(Path(entry['path']))
        for trace,event in enumerate(data['events']):
            intervals=[]
            for part in event['intervals']:
                base=sum(data['base'][trace][part['start']:part['end']]);shock=sum(data['shock'][trace][part['start']:part['end']])
                intervals.append(dict(start=part['start'],end=part['end'],factor=part['factor'],base_total=base,
                    shock_total=shock,actual_change_ratio=(shock-base)/base if base else None,
                    clipped_periods=sum(part['factor']*x>20 for x in data['base'][trace][part['start']:part['end']]) if part['factor']>1 else 0))
            summary['actual_profiles'].append(dict(batch=entry['batch'],trace=trace,type=event['type'],intervals=intervals,
                unchanged_consumed_path=data['base'][trace][:200]==data['shock'][trace][:200]))
    summary['node_periods']=len(rows)
    summary['limits']='Development-only, n=10 paths per shock class; no inferential claim or test-set status.'
    write(out/'summary.json',summary)
    write(out/'completed.json',dict(status='completed',phase='development_only',episodes=160,node_periods=96000,
        completed_runs=len(runs),api_requests=len(calls),all_attempt_http_requests=len(all_calls)+prior_http,
        all_attempt_semantic_requests=sum(c.get('attempt')==1 for c in all_calls)+prior_semantic,
        quota_recovery_runs=sum(1 for x in runs if 'quota_recovery' in x['run']),
        summary_sha256=digest(out/'summary.json'),
        all_registered_cases_retained=True,training_updates=0))
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'results/online_llm_shock_types/development_v4')
    p.add_argument('--register-only',action='store_true')
    p.add_argument('--preflight',action='store_true')
    p.add_argument('--run',action='store_true')
    args=p.parse_args();out=args.output.resolve()
    if sum((args.register_only,args.preflight,args.run))!=1:p.error('Choose exactly one execution phase')
    if args.register_only:
        try:
            manifest=register(out)
        except Exception as exc:
            if out.exists() and not (out/'registration_failed.json').exists():
                write(out/'registration_failed.json',dict(reason=type(exc).__name__,detail=str(exc)[:1000],
                    inputs_preserved=True,no_api_or_rollout=True))
            raise
        print('REGISTERED',manifest['expected_episodes'],manifest['expected_node_periods'],flush=True);return
    manifest=verify_registration(out)
    if args.preflight:
        if not os.environ.get('DEEPSEEK_API_KEY'):raise RuntimeError('API key unavailable for no-call request-contract preflight')
        checks=[]
        for entry in manifest['input_batches']:
            for seed in SEEDS:
                command=[sys.executable,str(RUNNER),'--run-name',f'preflight_seed{seed}_batch{entry["batch"]}',
                    '--input-file',entry['path'],'--training-directory',str(training(seed)),
                    '--operator-library',str(LIBRARY),'--output-root',str(out/'preflight'),'--preflight']
                result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,check=True)
                checks.append(dict(seed=seed,batch=entry['batch'],contract=json.loads(result.stdout)))
        write(out/'preflight.json',dict(status='passed_no_api_or_rollout',checks=checks,
            source_sha256=manifest['freeze_sha256']))
        print('PREFLIGHT_PASSED checks=',len(checks),'API_calls=0',flush=True);return
    if not os.environ.get('DEEPSEEK_API_KEY'):raise RuntimeError('API key unavailable; no experiment started')
    if any((out/name).exists() for name in ('launch.json','failed.json','completed.json')):
        raise RuntimeError('Experiment already launched, failed or completed; refuse repeat')
    if not (out/'preflight.json').exists() or read(out/'preflight.json').get('status')!='passed_no_api_or_rollout':
        raise RuntimeError('No successful registered no-call preflight')
    launch=dict(pid=os.getpid(),started=time.time(),manifest_sha256=digest(out/'manifest.json'),phase='development')
    with (out/'launch.json').open('x',encoding='utf-8') as stream:json.dump(launch,stream,indent=2)
    finished={};attempt_log=[];write(out/'progress.json',dict(status='running',completed_runs=[]))
    try:
        for seed in SEEDS:
            for entry in manifest['input_batches']:
                manifest=verify_registration(out)
                task=f'seed{seed}_batch{entry["batch"]}';retry=0
                while True:
                    label=task if retry==0 else f'{task}_quota_recovery{retry}'
                    command=[sys.executable,'-u',str(RUNNER),'--run-name',label,
                        '--input-file',entry['path'],'--training-directory',str(training(seed)),
                        '--operator-library',str(LIBRARY),'--output-root',str(out/'runs')]
                    write(out/'progress.json',dict(status='running',current_task=task,attempt=retry+1,
                        completed_runs=list(finished.values())))
                    with (out/f'{label}.log').open('x',encoding='utf-8') as stream:
                        proc=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
                    directory=out/'runs'/label
                    if proc.returncode==0:break
                    http_failure=fatal_http(directory)
                    attempt_log.append(dict(task=task,run_label=label,exit_code=proc.returncode,
                        fatal_http=http_failure,log_sha256=digest(out/f'{label}.log'),
                        raw_http_requests=len(read(directory/'calls.json')) if (directory/'calls.json').exists() else 0))
                    write(out/'attempts.json',attempt_log)
                    if http_failure=='HTTP_402' and retry==0:
                        wait_for_balance(out,task,1);retry=1;continue
                    raise RuntimeError(f'{task} failed with {http_failure or "non-quota process error"}; raw outputs retained')
                directory=out/'runs'/label
                assert (directory/'completed.json').exists()
                done=read(directory/'completed.json')
                entry_audit=dict(seed=seed,batch=entry['batch'],run_label=label,episodes=16,node_periods=9600,
                    completed_sha256=digest(directory/'completed.json'),input_sha256=entry['sha256'],
                    runtime_failures=done.get('runtime_failures',[]))
                finished[task]=entry_audit
                write(out/'progress.json',dict(status='running',completed_runs=list(finished.values())))
                verify_registration(out)
        summary=summarize(out,manifest,finished)
        print('SHOCK_TYPE_DEVELOPMENT_COMPLETED',json.dumps(dict(overall=summary['overall'],by_type=summary['by_shock_type']),ensure_ascii=False),flush=True)
    except Exception as exc:
        write(out/'failed.json',dict(failure=type(exc).__name__,detail=str(exc)[:1000],
            completed_runs=list(finished.values()),raw_outputs_preserved=True,no_blind_restart=True))
        raise


if __name__=='__main__':main()
