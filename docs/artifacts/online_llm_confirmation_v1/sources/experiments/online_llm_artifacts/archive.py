"""Audit completed frozen online runs and retain portable compressed artifacts."""
import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics

ROOT=Path(__file__).resolve().parents[2]
METHODS=('happo','llm_library','online_once','online_feedback','random_screen')
HEAVY={'periods.csv','scores.json','information_audits.json','delivered_reports.json'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_files(contract,check_source=True):
    if check_source:
        for name,expected in contract['source_sha256'].items():
            assert digest(ROOT/name)==expected,('source_changed',name)
    for name,expected in contract['model_files'].items():
        assert digest(Path(name))==expected,('model_file_changed',name)
    training=Path(contract.get('training_directory',''))
    if not str(training) or str(training)=='.':
        seed=contract['training_seed']
        training=ROOT/'results/learning_curve'/('curve_seed11_until_stable_v1' if seed==11 else f'curve_seed{seed}_formal_v1')
    for name,expected in contract['training_metadata'].items():
        assert digest(training/name)==expected,('training_metadata_changed',name)


def usage(records):
    total={}
    for record in records:
        for key,value in (record.get('usage') or {}).items():
            if isinstance(value,(int,float)):
                total[key]=total.get(key,0)+value
    return total


def forbidden_context(value):
    if isinstance(value,dict):
        assert not {'intensity','duration','start_index','validation_zero','validation_candidate','review_feedback'} & value.keys()
        for child in value.values():
            forbidden_context(child)
    elif isinstance(value,list):
        for child in value:
            forbidden_context(child)


def eligible(candidate,zero):
    return candidate['valid'] and candidate['cost']<=.99*zero['cost'] and candidate['downstream']<=zero['downstream']


def audit_run(directory,expected_input,contract,allow_runtime_fallbacks=False):
    """No environment rollout or API; independently recompute recorded contracts."""
    done=read(directory/'completed.json');protocol=read(directory/'protocol.json')
    assert done['episodes']==40 and done['rows']==24000 and done['training_updates']==0
    assert done['runtime_failures']==read(directory/'runtime_failures.json')
    if not allow_runtime_fallbacks:
        assert not done['runtime_failures']
    for key,value in contract.items():
        assert protocol[key]==value,('child_contract',key)
    expected_model=contract['expected_parameter_sha256']
    assert set(done['parameter_checks'])==set(METHODS)
    assert all(c['unchanged'] and c['before']==c['after']==expected_model for c in done['parameter_checks'].values())
    demands=read(directory/'demands.json');assert demands==expected_input
    with (directory/'periods.csv').open(encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    assert len(rows)==24000
    grouped={}
    for row in rows:
        assert float(row['cost'])==int(row['inventory'])+int(row['backlog'])
        assert 0<=int(row['actual_order'])<=20
        grouped.setdefault((row['group'],row['scenario'],int(row['trace'])),[]).append(row)
    episodes=read(directory/'episodes.json')
    assert len(episodes)==40 and set(grouped)=={(g,s,t) for g in METHODS for s in ('base','shock') for t in range(4)}
    records=[]
    for episode in episodes:
        local=grouped[episode['group'],episode['scenario'],episode['trace']]
        assert len(local)==600 and {(int(r['period']),int(r['node'])) for r in local}=={(p,n) for p in range(1,201) for n in range(3)}
        assert math.isclose(statistics.mean(float(r['cost']) for r in local),episode['cost'],abs_tol=1e-9)
        assert math.isclose(statistics.mean(int(r['backlog']) for r in local if r['node']=='0'),episode['downstream_backlog'],abs_tol=1e-9)
        assert episode['episode_http']<=16
        if episode['group']=='online_once':
            assert episode['generation_events']==(1 if episode['scenario']=='shock' else 0)
        if episode['group'] in ('online_feedback','random_screen'):
            assert episode['generation_events']==(4 if episode['scenario']=='shock' else 0)
        records.append(dict(seed=contract['training_seed'],**episode))
    keys=('period','node','cost','inventory','backlog','actual_order')
    for trace in range(4):
        for scenario in ('base','shock'):
            end=201 if scenario=='base' else demands['events'][trace]['start_index']+3
            baseline=[tuple(r[k] for k in keys) for r in grouped['happo',scenario,trace] if int(r['period'])<end]
            for group in METHODS[1:]:
                assert baseline==[tuple(r[k] for k in keys) for r in grouped[group,scenario,trace] if int(r['period'])<end]
    infos=read(directory/'information_audits.json');assert len(infos)==8000
    info_lookup={}
    for info in infos:
        p=info['decision_period']-1;through=p//3*3
        trace=demands[info['scenario']][info['trace']]
        reconstructed=[sum(trace[i:i+3])/3 for i in range(0,through,3) for _ in range(3)]
        assert info['reconstructed_history']==reconstructed and info['delivered_through_period']==through
        assert info['observed_periods']==p and info['report_age']==p-through and info['interval']==3
        info_lookup[info['group'],info['scenario'],info['trace'],p+1]=info
    assert len(info_lookup)==8000
    deliveries=read(directory/'delivered_reports.json');assert len(deliveries)==40*66
    for report in deliveries:
        end=report['end_period'];trace=demands[report['scenario']][report['trace']]
        assert end%3==0 and report['start_period']==end-2
        assert report['delivered_after_period']==end and report['available_from_decision_period']==end+1
        assert report['demand_total']==sum(trace[end-3:end]) and report['demand_mean']==sum(trace[end-3:end])/3
    calls=read(directory/'calls.json');assert len(calls)==done['calls']
    per_episode={};per_request={}
    for call in calls:
        assert call['group'] in ('online_once','online_feedback') and call['scenario']=='shock'
        key=(call['group'],call['trace']);per_episode[key]=per_episode.get(key,0)+1
        request_key=(*key,call['event'],call['stage']);per_request.setdefault(request_key,[]).append(call)
        assert call['event']<= (1 if call['group']=='online_once' else 4) and call['attempt'] in (1,2)
        assert call['request']['model']==contract['model']
        assert 'Authorization' not in call['request']
        context=json.loads(call['request']['messages'][1]['content']);forbidden_context(context)
        info=info_lookup[call['group'],call['scenario'],call['trace'],call['decision_period']]
        assert context['observed_periods']==call['decision_period']-1 and context['nodes']==info['rule_features']
        assert context['available_report']=={k:info[k] for k in ('interval','observed_periods','delivered_through_period','report_age','reconstructed_history','latest_report')}
        assert len(context['last_two_events'])<=2
        assert all(m['event']<call['event'] and m['observed_periods']<context['observed_periods'] for m in context['last_two_events'])
        assert len(context['last_two_events'])==min(2,call['event']-1)
        if call['stage']=='revision':
            assert len(context['search_feedback'])==4 and context['candidate_count']==1
        else:
            assert context['candidate_count']==3 and 'search_feedback' not in context
    assert all(n<=16 for n in per_episode.values())
    assert all([c['attempt'] for c in cs] in ([1],[1,2]) for cs in per_request.values())
    assert all(n<=4 for (group,_),n in per_episode.items() if group=='online_once')
    for episode in episodes:
        expected_calls=per_episode.get((episode['group'],episode['trace']),0) if episode['scenario']=='shock' else 0
        assert episode['episode_http']==expected_calls
    scores=read(directory/'scores.json');generations={}
    for result in scores:
        if result.get('screening_event') is False:
            assert result.get('execution_failure') and result['chosen']=='zero'
            continue
        assert result['scenario']=='shock' and result['group']!='happo'
        assert len(result['forecasts'])==2 and all(len(paths)==3 for paths in result['forecasts'])
        horizon=min(20,201-result['decision_period'])
        assert all(len(path)==horizon for paths in result['forecasts'] for path in paths)
        search=result['search'];assert len(search)==4 and search[0]['id']=='zero' and search[0]['valid']
        passed=[c for c in search[1:] if eligible(c,search[0])]
        chosen=min(passed,key=lambda c:c['cost'])['id'] if passed else 'zero'
        assert result['validation_candidate']['id']==chosen
        if chosen!='zero' and not eligible(result['validation_candidate'],result['validation_zero']):
            chosen='zero'
        if result.get('execution_failure'):
            assert allow_runtime_fallbacks and chosen==result['selected_before_execution'] and result['chosen']=='zero'
        else:
            assert chosen==result['chosen']
        if result.get('generation_event'):
            generations.setdefault((result['group'],result['trace']),[]).append(result)
            assert len(result['candidates'])==4
            if result['group'] in ('online_once','online_feedback','random_screen'):
                assert len(result['search_revision_feedback'])==4
    for trace in range(4):
        a=generations['online_feedback',trace];b=generations['random_screen',trace]
        assert [r['decision_period'] for r in a]==[r['decision_period'] for r in b]
        assert len(a)==len(b)==4
    return dict(records=records,api_requests=len(calls),api_failures=sum(c['status']!='valid' for c in calls),
        usage=usage(calls),raw_rows=len(rows),information_rows=len(infos),selection_events=len(scores),
        wall_seconds=done['wall_seconds'],api_seconds=sum(c.get('seconds',0) for c in calls),
        screening_seconds=sum(s.get('seconds',0)+s.get('revision_scoring_seconds',0) for s in scores),
        changed_node_orders=sum(r['actual_order']!=r['happo_order'] for r in rows))


def assert_no_secret(source):
    key=os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        return 'No configured key in archive process; requests inspected for missing authorization header'
    for path in source.rglob('*'):
        if path.is_file() and path.suffix in ('.json','.log','.py','.csv'):
            assert key.encode() not in path.read_bytes(),('secret_in_file',str(path))
    return 'Configured credential absent from all text artifacts'


def archive(source,export):
    if export.exists():
        raise RuntimeError('Refuse archive overwrite')
    manifest=read(source/'manifest.json');completion=read(source/'completed.json')
    assert completion['status']=='completed' and completion['episodes']==80
    assert digest(source/'inputs.json')==manifest['input_sha256']
    assert digest(Path(manifest['library_path']))==manifest['library_sha256']
    for rel,expected in manifest['source_sha256'].items():
        assert digest(ROOT/rel)==expected and digest(source/'sources'/rel)==expected
    audits=[]
    for seed in (11,12):
        contract=manifest['contracts'][str(seed)];verify_files(contract)
        audits.append(audit_run(source/f'seed{seed}',read(source/'inputs.json'),contract))
    summary=read(source/'summary.json')
    fitness=[e for a in audits for e in a['records']]
    assert fitness==summary['fitness']
    assert sum(a['raw_rows'] for a in audits)==48000 and len(fitness)==80
    for key in ('api_requests','api_failures','api_seconds','screening_seconds','changed_node_orders'):
        actual=sum(a[key] for a in audits)
        assert math.isclose(actual,summary[key],abs_tol=1e-8),(key,actual,summary[key])
    all_usage={}
    for a in audits:
        for key,value in a['usage'].items():
            all_usage[key]=all_usage.get(key,0)+value
    assert all_usage==summary['usage']
    for pair in summary['paired_deltas']:
        selected=[next(e for e in fitness if e['seed']==pair['seed'] and e['trace']==pair['trace'] and e['scenario']=='shock' and e['group']==g) for g in ('happo',pair['group'])]
        assert pair['cost_delta']==selected[1]['cost']-selected[0]['cost']
        assert pair['backlog_delta']==selected[1]['downstream_backlog']-selected[0]['downstream_backlog']
    assert summary['all_unfavorable_pairs']==[p for p in summary['paired_deltas'] if p['cost_delta']>0 or p['backlog_delta']>0]
    for item in summary['per_model']:
        pairs=[p for p in summary['paired_deltas'] if p['seed']==item['seed'] and p['group']==item['group']]
        assert len(pairs)==item['pairs']==4
        assert math.isclose(statistics.mean(p['cost_delta'] for p in pairs),item['mean_cost_delta'],abs_tol=1e-9)
        assert math.isclose(statistics.mean(p['backlog_delta'] for p in pairs),item['mean_backlog_delta'],abs_tol=1e-9)
    credential_audit=assert_no_secret(source)
    export.mkdir(parents=True)
    originals={};copied={}
    for path in source.rglob('*'):
        if not path.is_file() or any(part in ('__pycache__','models','final_models') for part in path.relative_to(source).parts):
            continue
        rel=path.relative_to(source)
        originals[str(rel)]=digest(path)
        target=export/rel;target.parent.mkdir(parents=True,exist_ok=True)
        if path.name in HEAVY:
            target=target.with_name(target.name+'.gz')
            with path.open('rb') as src,target.open('wb') as raw:
                with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as dst:
                    shutil.copyfileobj(src,dst)
            with gzip.open(target,'rb') as stream:
                assert hashlib.sha256(stream.read()).hexdigest()==originals[str(rel)]
        else:
            shutil.copy2(path,target);assert digest(target)==originals[str(rel)]
        copied[str(target.relative_to(export))]=digest(target)
    library=export/'frozen_library.json';shutil.copy2(Path(manifest['library_path']),library)
    assert digest(library)==manifest['library_sha256']
    copied['frozen_library.json']=digest(library)
    write(export/'verification.json',dict(status='verified',episodes=80,node_periods=48000,
        audits=[{k:v for k,v in a.items() if k!='records'} for a in audits],usage=all_usage,
        raw_cost_backlog_reports_normal_actions_API_budgets_summary='passed',
        source_snapshot_and_current_model_metadata_hashes='passed',credential_audit=credential_audit,
        api_requests=sum(a['api_requests'] for a in audits),development_only=True,
        currency_cost=None,cost_note='Tokens retained; currency billing not independently obtained',
        original_outputs_preserved=True,model_weights_not_copied=True))
    write(export/'export_hashes.json',dict(original_sha256=originals,
        archive_sha256={**copied,'verification.json':digest(export/'verification.json')}))
    print('ARCHIVED_VERIFIED',str(export),'80 episodes48000 rows',all_usage,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'results/online_llm/development_v1')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/artifacts/online_llm_development_v1')
    options=parser.parse_args();archive(options.source.resolve(),options.output.resolve())
