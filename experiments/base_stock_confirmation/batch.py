"""Independent common-path confirmation with frozen local Base-stock z2/z8."""
import argparse
import csv
import gzip
import importlib.util
import json
import math
import os
import re
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT/'results/base_stock_confirmation/confirmation_v1'
PROTOCOL = ROOT/'docs/superpowers/plans/2026-10-05-base-stock-confirmation.md'
PROOF = ROOT/'results/base_stock_confirmation/no_api_preflight_v1.json'
OLD_CONFIRMATION = ROOT/'results/joint_baseline_confirmation/confirmation_v1'
CANDIDATE_SEEDS = tuple(range(20271601, 20271651))
EXPECTED_EPISODES = 1360
EXPECTED_ROWS = 816000
BASE_STOCK_CONFIGS = [dict(name=f'z{z:02d}', z=z, information='local', rounding='ceil',
                           initial_history=[10]*40) for z in (2, 8)]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


b = load('formal_base_stock_legacy_batch', ROOT/'experiments/joint_baseline_confirmation/batch.py')
a = load('formal_base_stock_legacy_analyze', ROOT/'experiments/joint_baseline_confirmation/analyze.py')
core = b.core
policy = load('formal_base_stock_policy', ROOT/'experiments/base_stock_baseline/policy.py')
sys.modules['policy'] = policy
bs = load('formal_base_stock_episode', ROOT/'experiments/base_stock_baseline/batch.py')
diagnosis = load('formal_base_stock_scalar_diagnosis', ROOT/'experiments/online_llm_artifacts/audit_base_stock_numerical.py')
read, write, digest = core.read, core.write, core.digest
SEEDS, METHODS, PROFILES = b.SEEDS, b.METHODS, b.PROFILES
b.OUTPUT = OUTPUT
b.PROTOCOL = PROTOCOL
b.CANDIDATE_SEEDS = CANDIDATE_SEEDS


def bind_legacy_audit():
    # The old function has an unqualified import inside its real audit tail.
    sys.modules['analyze'] = a


def audit_child(directory, entry, seed):
    bind_legacy_audit()
    return b.audit_child(directory, entry, seed)


def source_hashes():
    hashes = core.source_hashes()
    files = list(Path(__file__).parent.glob('*.py'))
    files += list((ROOT/'experiments/base_stock_baseline').glob('*.py'))
    files += [Path(diagnosis.__file__), PROTOCOL,
              ROOT/'docs/superpowers/plans/2026-10-05-nonstationary-base-stock-baseline.md',
              ROOT/'docs/2026-10-05-base-stock-development-protocol.md']
    files += [ROOT/'results/base_stock_baseline/development_v1'/name for name in
              ('manifest.json','freeze.json','summary.json','independent_audit_v2.json')]
    return dict(hashes, **{str(p.relative_to(ROOT)):digest(p) for p in files})


def screen_paths(records, historical, accepted):
    local = {}
    collisions = []
    equal = []
    for trace, scenario, path in records:
        if path in historical:
            collisions.append(dict(kind='historical_exact_path', trace=trace, scenario=scenario))
        if path in accepted:
            collisions.append(dict(kind='accepted_path_duplicate', trace=trace, scenario=scenario))
        if path in local:
            prior_trace, prior_scenario = local[path]
            if prior_trace == trace and {prior_scenario, scenario} == {'base', 'shock'}:
                equal.append(trace)
            else:
                collisions.append(dict(kind='within_batch_duplicate', trace=trace, scenario=scenario))
        else:
            local[path] = (trace, scenario)
    return collisions, equal


def credential():
    # Retrieve only the Windows User value; never put it in files or argv.
    result = subprocess.run(['powershell', '-NoProfile', '-Command',
        "[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')"],
        capture_output=True, text=True, check=True)
    value = result.stdout.strip()
    if not value:
        raise RuntimeError('Windows User DEEPSEEK_API_KEY unavailable')
    os.environ['DEEPSEEK_API_KEY'] = value


def without_input(contract):
    return {k:v for k,v in contract.items() if k not in ('input_sha256', 'key_present')}


def no_api_proof():
    """Read-only reaudit of exposed genuine five-model runs; no new rollout/API."""
    import socket
    network_attempts = []
    original_connect = socket.socket.connect
    original_create = socket.create_connection
    def forbidden(*args, **kwargs):
        network_attempts.append(True)
        raise AssertionError('Network forbidden during offline proof')
    socket.socket.connect = forbidden
    socket.create_connection = forbidden
    try:
        fixture_manifest = read(OLD_CONFIRMATION/'manifest.json')
        entry = fixture_manifest['input_batches'][0]
        input_path = Path(entry['path'])
        checks = []
        for seed in SEEDS:
            directory = OLD_CONFIRMATION/'runs'/f'seed{seed}_batch01'
            current = core.contracts(input_path, b.LIBRARY, b.training(seed), require_key=False)
            old = entry['contracts'][str(seed)]
            assert current['source_sha256']==old['source_sha256'], 'Original frozen runner dependency source changed'
            assert {k:v for k,v in without_input(current).items() if k != 'source_sha256'} == {
                k:v for k,v in without_input(old).items() if k != 'source_sha256'}
            result = audit_child(directory, entry, seed)
            checks.append(dict(seed=seed, directory=str(directory), episodes=len(result['episodes']), rows=len(result['rows']),
                contract=current, oracle_parameter_checks=result['completed']['parameter_checks'],
                fixture_files={str(p):digest(p) for p in directory.glob('*.json')},
                periods_sha256=digest(directory/'periods.csv'),
                historical_http_requests=len(result['calls']), historical_requests_excluded_from_new_cost=True,
                source_changes={},original_source_sha256=old['source_sha256']))
        bs_checks = []
        exposed = read(input_path)
        for config in BASE_STOCK_CONFIGS:
            kwargs = {k:v for k,v in config.items() if k != 'name'}
            constant = bs.episode([10]*200, **kwargs)
            diagnosis.verify_episode(constant['rows'], [10]*200, config)
            left = bs.episode(exposed['base'][0], **kwargs)
            right = bs.episode(exposed['shock'][0], **kwargs)
            diagnosis.verify_episode(left['rows'], exposed['base'][0], config)
            diagnosis.verify_episode(right['rows'], exposed['shock'][0], config)
            stop = exposed['events'][0]['start_index']
            assert left['rows'][:stop*3] == right['rows'][:stop*3]
            assert all(r['mean'] == 10 and r['variance'] == 0 for r in constant['rows'] if r['period']==0)
            bs_checks.append(dict(config=config, constant_cost=constant['cost'],
                causal_prefix_periods=stop, independently_verified_rows=1800))
        assert not network_attempts
        PROOF.parent.mkdir(parents=True, exist_ok=True)
        write(PROOF, dict(status='passed', api_requests=0, new_inputs=False, new_rl_rollouts=False,
            new_bs_rollouts=6,new_bs_node_periods=3600,
            bs_input_provenance='Two constant [10]*200 checks and four episodes from exposed old batch01 trace0 base/shock',
            old_genuine_weight_fixture_reaudited=True, fixture_manifest_path=str(OLD_CONFIRMATION/'manifest.json'),
            fixture_manifest_sha256=digest(OLD_CONFIRMATION/'manifest.json'),input_path=str(input_path),input_sha256=digest(input_path),
            checks=checks, base_stock_checks=bs_checks, source_sha256=source_hashes(), runtime=b.runtime_contract()))
        print('OFFLINE_PROOF_PASSED API_calls=0 five_original_weight_fixtures=5', flush=True)
    finally:
        socket.socket.connect = original_connect
        socket.create_connection = original_create


def register(out=OUTPUT):
    if out.exists():
        raise RuntimeError('Refuse to overwrite an existing confirmation')
    credential()
    previous = read(ROOT/'results/online_llm_shock_types/confirmation_v5b/freeze.json')
    if os.environ.get('DEEPSEEK_MODEL', 'deepseek-flash') != previous['api_model']:
        raise RuntimeError('Deployment differs from frozen original confirmation')
    proof = read(PROOF)
    assert proof['status']=='passed' and proof['api_requests']==0 and not proof['new_inputs']
    assert proof['source_sha256'] == source_hashes() and proof['runtime']==b.runtime_contract()
    assert digest(Path(proof['fixture_manifest_path']))==proof['fixture_manifest_sha256']
    assert digest(Path(proof['input_path']))==proof['input_sha256']
    for check in proof['checks']:
        assert all(digest(Path(p)) == expected for p,expected in check['fixture_files'].items())
        assert digest(Path(check['directory'])/'periods.csv')==check['periods_sha256']
    contracts = {str(seed):core.contracts(b.REFERENCE,b.LIBRARY,b.training(seed)) for seed in SEEDS}
    out.mkdir(parents=True)
    freeze = dict(phase='independent_confirmation', development_only=False,
        source_sha256=source_hashes(), training_contracts=contracts, runtime=b.runtime_contract(),
        proof_path=str(PROOF), proof_sha256=digest(PROOF), protocol_sha256=digest(PROTOCOL),
        library_sha256=digest(b.LIBRARY), reference_input_sha256=digest(b.REFERENCE),
        methods_frozen_before_input_generation=True, base_stock_configs=BASE_STOCK_CONFIGS,
        api_model=previous['api_model'], candidate_demand_seeds=list(CANDIDATE_SEEDS),
        timing_offsets=list(b.TIMING_OFFSETS), per_episode_http_cap=16,
        first_pass_http_ceiling=3200, first_pass_semantic_ceiling=1600,
        total_http_ceiling=6400, total_semantic_ceiling=3200,
        quota_recovery='Only HTTP402; one full rerun per task after balance recovery, checks every 1800 seconds')
    write(out/'freeze.json', freeze)  # Persist every method/runtime lock BEFORE any candidate generation.
    historical, sources = b.historical_traces(out)
    accepted, seen, scan = [], set(), []
    for seed in CANDIDATE_SEEDS:
        if len(accepted)==10:
            break
        data = b.generated_batch(seed, len(accepted))
        records = b.input_path_records(data)
        collisions, equal = screen_paths(records, historical, seen)
        scan.append(dict(seed=seed, status='rejected_collision' if collisions else 'accepted',
            batch=None if collisions else len(accepted)+1, collisions=collisions,
            same_pair_zero_actual_change=equal,
            path_hashes=[dict(trace=t,scenario=s,sha256=b.trace_hash(p)) for t,s,p in records]))
        if collisions:
            continue
        accepted.append((seed,data,equal))
        seen.update(path for _,_,path in records)
    write(out/'collision_diagnosis.json',dict(status='passed' if len(accepted)==10 else 'insufficient',
        candidate_scan=scan, historical_source_manifest=sources, historical_trace_count=len(historical),
        accepted=len(accepted), accepted_path_count=len(seen), path_definition='first200 consumed integers'))
    if len(accepted)!=10:
        raise RuntimeError('Registered candidate range exhausted; refuse ad hoc replacement seeds')
    entries=[]
    (out/'inputs').mkdir()
    for number,(seed,data,equal) in enumerate(accepted,1):
        path=out/'inputs'/f'batch{number:02d}.json'
        write(path,data)
        batch_contracts={str(s):core.contracts(path,b.LIBRARY,b.training(s)) for s in SEEDS}
        assert all(without_input(batch_contracts[str(s)])==without_input(contracts[str(s)]) for s in SEEDS)
        entries.append(dict(batch=number,path=str(path),sha256=digest(path),demand_seed=seed,
            timing_offset=b.TIMING_OFFSETS[number-1],profiles=list(PROFILES),contracts=batch_contracts,
            same_pair_zero_actual_change=equal,
            path_hashes=[dict(trace=t,scenario=s,sha256=b.trace_hash(p)) for t,s,p in b.input_path_records(data)]))
    manifest=dict(status='registered',phase='independent_confirmation',development_only=False,
        freeze_sha256=digest(out/'freeze.json'),collision_diagnosis_sha256=digest(out/'collision_diagnosis.json'),
        input_batches=entries,training_seeds=list(SEEDS),methods=list(METHODS),shock_types=list(PROFILES),
        base_stock_configs=BASE_STOCK_CONFIGS,independent_paths_per_type=10,distinct_type_paths=40,
        expected_runs=50,expected_rl_episodes=1200,expected_base_stock_episodes=160,
        expected_episodes=1360,expected_rows=816000,expected_node_periods=816000,
        first_pass_http_ceiling=3200,first_pass_semantic_ceiling=1600,total_http_ceiling=6400,total_semantic_ceiling=3200,
        bootstrap=dict(replicates=20000,seed=20271651),primary='online_feedback minus local Base-stock z2 shock cost',
        historical_api_costs_excluded_from_batch=True,no_training=True,no_test_feedback=True)
    write(out/'manifest.json',manifest)
    return manifest


def verify_registration(out=OUTPUT):
    freeze=read(out/'freeze.json');manifest=read(out/'manifest.json')
    assert digest(out/'freeze.json')==manifest['freeze_sha256']
    assert digest(out/'collision_diagnosis.json')==manifest['collision_diagnosis_sha256']
    assert source_hashes()==freeze['source_sha256'] and b.runtime_contract()==freeze['runtime']
    assert digest(PROOF)==freeze['proof_sha256'] and digest(PROTOCOL)==freeze['protocol_sha256']
    assert digest(b.LIBRARY)==freeze['library_sha256'] and digest(b.REFERENCE)==freeze['reference_input_sha256']
    assert len(manifest['input_batches'])==10 and manifest['base_stock_configs']==BASE_STOCK_CONFIGS
    for entry in manifest['input_batches']:
        path=Path(entry['path']);assert digest(path)==entry['sha256']
        data=core.validate_inputs(read(path))
        assert entry['path_hashes']==[dict(trace=t,scenario=s,sha256=b.trace_hash(p)) for t,s,p in b.input_path_records(data)]
        for seed in SEEDS:
            current=core.contracts(path,b.LIBRARY,b.training(seed),require_key=False)
            assert {k:v for k,v in current.items() if k!='key_present'}=={k:v for k,v in entry['contracts'][str(seed)].items() if k!='key_present'}
            assert without_input(current)==without_input(freeze['training_contracts'][str(seed)])
    return manifest


def audit_base_stock(directory, entry, config):
    assert read(directory/'config.json')==config
    done=read(directory/'completed.json');scores=read(directory/'episodes.json')
    assert len(scores)==8 and done['episodes']==8 and done['rows']==4800
    assert all(digest(directory/name)==expected for name,expected in done['files_sha256'].items())
    with gzip.open(directory/'periods.csv.gz','rt',encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    assert len(rows)==4800
    keyed={(int(r['trace']),r['scenario'],int(r['period']),int(r['node'])):r for r in rows}
    assert len(keyed)==4800 and set(keyed)=={(t,s,p,n) for t in range(4) for s in ('base','shock') for p in range(200) for n in range(3)}
    data=read(Path(entry['path']))
    expected={(t,s) for t in range(4) for s in ('base','shock')}
    assert {(e['trace'],e['scenario']) for e in scores}==expected
    boundaries_start=len(diagnosis.BOUNDARIES)
    for score in scores:
        trace,scenario=score['trace'],score['scenario']
        block=[keyed[trace,scenario,p,n] for p in range(200) for n in range(3)]
        assert all(r['type']==data['events'][trace]['type'] and r['config']==config['name'] and
                   int(r['batch'])==entry['batch'] and r['group']==f"base_stock_{config['name']}" for r in block)
        cost=diagnosis.verify_episode(block,data[scenario][trace],config)
        assert math.isclose(cost,score['cost'],abs_tol=1e-8)
        backlog=sum(float(r['backlog']) for r in block if int(r['node'])==0)/200
        assert math.isclose(backlog,score['downstream_backlog'],abs_tol=1e-8)
        assert score['ledger_verified'] and score['group']==f"base_stock_{config['name']}"
    for trace,event in enumerate(data['events']):
        for p in range(event['start_index']):
            for n in range(3):
                left=keyed[trace,'base',p,n];right=keyed[trace,'shock',p,n]
                assert {k:v for k,v in left.items() if k!='scenario'}=={k:v for k,v in right.items() if k!='scenario'}
    return dict(rows=4800,episodes=8,independent_state_cost_ledger=True,
                numerical_boundaries=diagnosis.BOUNDARIES[boundaries_start:])


def evaluate_base_stock(out, entry, config):
    verify_registration(out)
    directory=out/'base_stock'/config['name']/f"batch{entry['batch']:02d}"
    directory.mkdir(parents=True,exist_ok=False)
    write(directory/'config.json',config)
    data=read(Path(entry['path']));scores=[]
    with gzip.open(directory/'periods.csv.gz','wt',encoding='utf-8',newline='') as stream:
        writer=None
        for trace,event in enumerate(data['events']):
            for scenario in ('base','shock'):
                result=bs.episode(data[scenario][trace],**{k:v for k,v in config.items() if k!='name'})
                identity=dict(group=f"base_stock_{config['name']}",config=config['name'],batch=entry['batch'],
                              trace=trace,type=event['type'],scenario=scenario)
                for row in result.pop('rows'):
                    row=dict(**identity,**row)
                    if writer is None:
                        writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader()
                    writer.writerow(row)
                scores.append(dict(**identity,**result))
    write(directory/'episodes.json',scores)
    write(directory/'completed.json',dict(episodes=8,rows=4800,api_requests=0,training_updates=0,
        input_sha256=entry['sha256'],files_sha256={n:digest(directory/n) for n in ('config.json','episodes.json','periods.csv.gz')}))
    audit=audit_base_stock(directory,entry,config)
    write(directory/'independent_audit.json',audit)
    verify_registration(out)


def registered_preflight(out=OUTPUT):
    manifest=verify_registration(out)
    checks=[]
    for entry in manifest['input_batches']:
        for seed in SEEDS:
            checks.append(dict(seed=seed,batch=entry['batch'],contract=core.contracts(
                Path(entry['path']),b.LIBRARY,b.training(seed),require_key=False)))
    write(out/'preflight.json',dict(status='passed_no_api_or_rollout',api_requests=0,checks=checks,
        freeze_sha256=digest(out/'freeze.json'),manifest_sha256=digest(out/'manifest.json')))
    print('PREFLIGHT_PASSED checks=50 API_calls=0',flush=True)


def wait_for_balance(out, task):
    history=[]
    path=out/'quota_wait_history.json'
    if path.exists():history=read(path)
    while True:
        available=b.api_balance_available()
        history.append(dict(task=task,checked_at=time.time(),balance_available=available))
        write(path,history)
        write(out/'quota_wait.json',dict(status='available_retrying_once' if available else 'waiting_for_balance',task=task))
        if available:return
        print('QUOTA_WAIT',task,'next_check_seconds=1800',flush=True)
        for _ in range(30):time.sleep(60)


def recorded_calls(out):
    # Malformed partial metadata must stop the budget audit, never disappear from it.
    calls=[]
    root=out/'runs'
    if not root.exists():return calls
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or not re.fullmatch(r'seed1[1-5]_batch(?:0[1-9]|10)(?:_quota_recovery1)?',directory.name):
            raise RuntimeError('Unexpected task entry in API ledger root')
        path=directory/'calls.json'
        try:records=read(path)
        except (ValueError,OSError) as exc:
            raise RuntimeError(f'Missing or unreadable API ledger for {directory.name}') from exc
        if not isinstance(records,list):raise RuntimeError('API ledger must contain a list')
        for item in records:
            if not isinstance(item,dict) or type(item.get('attempt')) is not int or item['attempt'] not in (1,2):
                raise RuntimeError('API ledger has invalid or missing attempt identity')
            if item.get('group')!='online_feedback' or item.get('scenario')!='shock' or 'run' in item:
                raise RuntimeError('API ledger violates frozen method/scenario/run identity')
            calls.append(dict(run=directory.name,**item))
    return calls


def check_budget(calls, retry):
    if any(not isinstance(c,dict) or type(c.get('attempt')) is not int or c['attempt'] not in (1,2) or
           not isinstance(c.get('run'),str) for c in calls):
        raise RuntimeError('Malformed API accounting record')
    first=[c for c in calls if '_quota_recovery' not in c['run']]
    if len(calls)+64>6400 or sum(c.get('attempt')==1 for c in calls)+32>3200:
        raise RuntimeError('Insufficient cumulative registered task budget')
    if retry==0 and (len(first)+64>3200 or sum(c.get('attempt')==1 for c in first)+32>1600):
        raise RuntimeError('Insufficient first-pass registered task budget')


def run(out=OUTPUT):
    credential();manifest=verify_registration(out)
    proof=read(out/'preflight.json')
    assert proof['status']=='passed_no_api_or_rollout' and proof['api_requests']==0
    assert proof['freeze_sha256']==manifest['freeze_sha256'] and proof['manifest_sha256']==digest(out/'manifest.json')
    with (out/'started.lock').open('x',encoding='utf-8') as stream:
        json.dump(dict(pid=os.getpid(),started=time.time(),manifest_sha256=digest(out/'manifest.json')),stream)
    with (out/'launch.json').open('x',encoding='utf-8') as stream:
        json.dump(dict(pid=os.getpid(),started=time.time(),phase='independent_confirmation'),stream)
    finished={};attempts=[]
    try:
        for seed in SEEDS:
            for entry in manifest['input_batches']:
                task=f"seed{seed}_batch{entry['batch']:02d}";retry=0
                while True:
                    verify_registration(out)
                    calls=recorded_calls(out)
                    check_budget(calls,retry)
                    label=task if retry==0 else task+'_quota_recovery1'
                    command=[sys.executable,'-u',str(b.RUNNER),'--run-name',label,'--input-file',entry['path'],
                        '--training-directory',str(b.training(seed)),'--operator-library',str(b.LIBRARY),'--output-root',str(out/'runs')]
                    write(out/'progress.json',dict(status='running',current_task=task,attempt=retry+1,completed_runs=list(finished.values())))
                    with (out/f'{label}.log').open('x',encoding='utf-8') as stream:
                        process=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
                    directory=out/'runs'/label
                    if process.returncode==0:break
                    fatal=b.fatal_http(directory)
                    failed=dict(task=task,run_label=label,exit_code=process.returncode,fatal_http=fatal,
                                log_sha256=digest(out/f'{label}.log'),raw_outputs_preserved=True)
                    attempts.append(failed);write(out/'attempts.json',attempts)
                    with (out/f'{label}_failed_attempt.json').open('x',encoding='utf-8') as stream:json.dump(failed,stream,indent=2)
                    if fatal=='HTTP_402' and retry==0:
                        wait_for_balance(out,task);retry=1;continue
                    raise RuntimeError(f'{task} failed with {fatal or "process/audit error"}; no blind restart')
                audited=audit_child(directory,entry,seed)
                finished[task]=dict(seed=seed,batch=entry['batch'],run_label=label,episodes=24,node_periods=14400,
                    completed_sha256=digest(directory/'completed.json'),input_sha256=entry['sha256'],
                    runtime_failures=audited['runtime_failures'],
                    files_sha256={p.name:digest(p) for p in directory.iterdir() if p.is_file()})
                write(out/'progress.json',dict(status='running',completed_runs=list(finished.values())))
                verify_registration(out)
        for config in BASE_STOCK_CONFIGS:
            for entry in manifest['input_batches']:evaluate_base_stock(out,entry,config)
        base_stock_finished=[]
        for config in BASE_STOCK_CONFIGS:
            for entry in manifest['input_batches']:
                directory=out/'base_stock'/config['name']/f"batch{entry['batch']:02d}"
                audit_base_stock(directory,entry,config)
                base_stock_finished.append(dict(config=config['name'],batch=entry['batch'],
                    completed_sha256=digest(directory/'completed.json'),independent_audit_sha256=digest(directory/'independent_audit.json')))
        for item in finished.values():
            directory=out/'runs'/item['run_label']
            assert all(digest(directory/n)==sha for n,sha in item['files_sha256'].items())
        verify_registration(out)
        analysis=load('formal_base_stock_confirmation_analysis',Path(__file__).with_name('analyze.py'))
        analysis.summarize(out,manifest,finished)
        verify_registration(out)
        write(out/'completed.json',dict(phase='independent_confirmation',development_only=False,episodes=1360,
            rows=816000,node_periods=816000,rl_runs=50,base_stock_runs=20,finished=finished,
            base_stock_finished=base_stock_finished,
            api_requests=len(recorded_calls(out)),usage=b.usage_totals(recorded_calls(out)),
            summary_sha256=digest(out/'summary.json'),manifest_sha256=digest(out/'manifest.json')))
        write(out/'progress.json',dict(status='completed',completed_runs=list(finished.values())))
        print('BASE_STOCK_CONFIRMATION_COMPLETED episodes=1360 rows=816000',flush=True)
    except Exception as exc:
        detail=str(exc)
        key=os.environ.get('DEEPSEEK_API_KEY')
        if key:detail=detail.replace(key,'[REDACTED]')
        write(out/'failed.json',dict(failure=type(exc).__name__,detail=detail[:1000],
                                   completed_runs=list(finished.values()),raw_outputs_preserved=True,no_blind_restart=True))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--offline-proof',action='store_true')
    mode.add_argument('--register-only',action='store_true')
    mode.add_argument('--preflight',action='store_true')
    mode.add_argument('--run',action='store_true')
    args=parser.parse_args()
    if args.offline_proof:no_api_proof()
    elif args.register_only:
        try:register()
        except Exception as exc:
            if OUTPUT.exists():write(OUTPUT/'registration_failed.json',dict(failure=type(exc).__name__,no_rollout=True))
            raise
        print('REGISTERED episodes=1360 rows=816000',flush=True)
    elif args.preflight:registered_preflight()
    else:run()


if __name__=='__main__':main()
