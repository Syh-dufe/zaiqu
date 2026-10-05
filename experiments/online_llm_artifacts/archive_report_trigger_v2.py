"""Independent period/report audit and lossless archival; no API or training."""
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
from collections import Counter, defaultdict
import statistics
import shutil

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'results/online_llm_report_trigger/development_v2'
FAILED=ROOT/'results/online_llm_report_trigger/development_v1'
EXPORT=ROOT/'docs/artifacts/online_llm_report_trigger_development_v2'
spec=importlib.util.spec_from_file_location('archival_util',Path(__file__).with_name('archive_shock_confirmation_v5b.py'))
util=importlib.util.module_from_spec(spec);spec.loader.exec_module(util)
read,digest,copy_and_hash=util.read,util.digest,util.copy_and_hash
METHODS=('happo','online_feedback','report_trigger_feedback')


def main():
    assert not EXPORT.exists(),'Refuse archive overwrite'
    freeze=read(SOURCE/'freeze.json');manifest=read(SOURCE/'manifest.json');summary=read(SOURCE/'summary.json')
    done=read(SOURCE/'completed.json');progress=read(SOURCE/'progress.json')
    assert done['episodes']==240 and done['node_periods']==144000 and progress['status']=='completed'
    assert digest(SOURCE/'summary.json')==done['summary_sha256']
    assert digest(SOURCE/'freeze.json')==manifest['freeze_sha256']
    assert len(progress['completed_runs'])==10
    for rel,h in freeze['source_sha256'].items():assert digest(ROOT/rel)==h,rel
    assert digest(ROOT/'docs/superpowers/plans/2026-10-05-online-report-trigger-development-v2.md')==freeze['protocol_sha256']
    all_episodes=[];all_calls=[];all_scores=[];pairs=[];failures=[];schedules=[];total_rows=0;normal_checks=0
    for entry in manifest['input_batches']:
        assert digest(entry['path'])==entry['sha256']
        for seed,c in entry['contracts'].items():
            for name,h in c['model_files'].items():assert digest(name)==h
            folder=ROOT/'results/learning_curve'/('curve_seed11_until_stable_v1' if seed=='11' else f'curve_seed{seed}_formal_v1')
            for name,h in c['training_metadata'].items():assert digest(folder/name)==h
    for item in progress['completed_runs']:
        seed,batch=item['seed'],item['batch'];folder=SOURCE/'runs'/item['run_label']
        c=read(folder/'completed.json');episodes=read(folder/'episodes.json');calls=read(folder/'calls.json');scores=read(folder/'scores.json')
        reports=read(folder/'delivered_reports.json');data=read(folder/'demands.json')
        entry=next(e for e in manifest['input_batches'] if e['batch']==batch)
        assert digest(folder/'demands.json')==entry['sha256']
        assert c['training_updates']==0 and set(c['parameter_checks'])==set(METHODS)
        assert all(x['unchanged'] and x['before']==x['after'] for x in c['parameter_checks'].values())
        assert digest(folder/'completed.json')==item['completed_sha256']
        with (folder/'periods.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
        assert len(rows)==14400 and len({(r['group'],r['scenario'],r['trace'],r['period'],r['node']) for r in rows})==14400
        assert len(episodes)==24
        for e in episodes:
            selected=[r for r in rows if r['group']==e['group'] and r['scenario']==e['scenario'] and int(r['trace'])==e['trace']]
            assert len(selected)==600 and all(float(r['cost'])==int(r['inventory'])+int(r['backlog']) for r in selected)
            assert all(0<=int(r['actual_order'])<=20 for r in selected)
            cost=statistics.mean(float(r['cost']) for r in selected)
            backlog=statistics.mean(int(r['backlog']) for r in selected if r['node']=='0')
            assert math.isclose(cost,e['cost'],abs_tol=1e-9) and math.isclose(backlog,e['downstream_backlog'],abs_tol=1e-9)
            if e['group']=='happo' or e['scenario']=='base':assert e['episode_http']==0 and e['generation_events']==0
            assert e['episode_http']<=16 and e['generation_events']<=4
            all_episodes.append(dict(seed=seed,batch=batch,**e))
        for trace,event in enumerate(data['events']):
            for scenario in ('base','shock'):
                stop=201 if scenario=='base' else event['start_index']+3
                fields=('period','node','inventory','backlog','actual_order','cost')
                select=lambda g:[tuple(r[k] for k in fields) for r in rows if r['group']==g and r['scenario']==scenario and int(r['trace'])==trace and int(r['period'])<stop]
                for method in METHODS[1:]:assert select('happo')==select(method);normal_checks+=1
            for method in METHODS:
                selected=[s for s in scores if s['group']==method and s['scenario']=='shock' and s['trace']==trace]
                generated=[s for s in selected if s.get('generation_event')]
                assert len(generated)<=4
                if method=='happo':assert not generated
                if method=='online_feedback':assert [s['decision_period'] for s in generated]==list(range(event['start_index']+3,event['start_index']+23,5))
                if method=='report_trigger_feedback':
                    last=None;reference=None;last_report=-1;count=0
                    for s in selected:
                        period=s['decision_period']-1
                        visible=[r for r in reports if r['group']==method and r['scenario']=='shock' and r['trace']==trace and r['end_period']<=period]
                        values=[r['demand_mean'] for r in visible[-2:]];mean=statistics.mean(values) if values else 0.
                        through=visible[-1]['end_period'] if visible else 0
                        gap=0 if last is None else period-last
                        change=0 if reference is None else abs(mean-reference)/max(1.,abs(reference))
                        trigger=through>last_report and count<4 and (count==0 or (gap>=20 and (change>=.25 or gap>=30)))
                        assert (period-event['start_index']-2)%5==0
                        assert s['generation_event']==trigger
                        d=s['generation_schedule'];assert d['events_before']==count and d['last_generation_period']==last
                        assert math.isclose(d['report_mean'],mean,abs_tol=1e-12) and d['reference_mean']==reference
                        if trigger:count+=1;last=period;reference=mean;last_report=through
                if method!='happo':schedules.append(dict(seed=seed,batch=batch,trace=trace,type=event['type'],method=method,
                    periods=[s['decision_period'] for s in generated],chosen=[s['chosen'] for s in generated],
                    changed_node_periods=sum(r['actual_order']!=r['happo_order'] for r in rows if r['group']==method and r['scenario']=='shock' and int(r['trace'])==trace)))
            lookup={e['group']:e for e in episodes if e['scenario']=='shock' and e['trace']==trace}
            orig,new=lookup['online_feedback'],lookup['report_trigger_feedback']
            pairs.append(dict(seed=seed,batch=batch,trace=trace,type=event['type'],cost_delta=new['cost']-orig['cost'],backlog_delta=new['downstream_backlog']-orig['downstream_backlog']))
        assert all(c['group'] in METHODS[1:] and c['scenario']=='shock' for c in calls)
        all_calls.extend(calls);all_scores.extend(scores);failures.extend(read(folder/'runtime_failures.json'));total_rows+=len(rows)
    assert len(all_episodes)==240 and total_rows==144000 and len(pairs)==40 and normal_checks==160
    for p,stored in zip(pairs,summary['paired_results']):
        assert all(p[k]==stored[k] for k in ('seed','batch','trace','type','cost_delta','backlog_delta'))
    pooled={k:statistics.mean(p[k] for p in pairs) for k in ('cost_delta','backlog_delta')}
    assert all(math.isclose(pooled[k],summary['overall'][k]['mean'],abs_tol=1e-12) for k in pooled)
    types={t:{k:statistics.mean(p[k] for p in pairs if p['type']==t) for k in pooled} for t in {p['type'] for p in pairs}}
    gate=all(v<0 for v in pooled.values()) and not any(all(v>0 for v in d.values()) for d in types.values())
    assert gate is summary['development_gate_passed']
    semantic=sum(c.get('attempt')==1 for c in all_calls);usage=Counter()
    for c in all_calls:
        for k,v in (c.get('usage') or {}).items():
            if isinstance(v,(int,float)):usage[k]+=v
    assert len(all_calls)==summary['api_requests'] and semantic==summary['semantic_requests'] and dict(usage)==summary['token_usage']
    assert len(all_calls)<=1280 and semantic<=640
    resources={g:dict(http=sum(c['group']==g for c in all_calls),semantic=sum(c['group']==g and c.get('attempt')==1 for c in all_calls),
        initial_failed=sum(s['group']==g and bool(s.get('failure')) for s in all_scores),revision_failed=sum(s['group']==g and bool(s.get('revision_failed')) for s in all_scores),
        failed_replies=sum(c['group']==g and c['status']!='valid' for c in all_calls)) for g in METHODS[1:]}
    absolute={g:{k:statistics.mean(e[k] for e in all_episodes if e['group']==g and e['scenario']=='shock') for k in ('cost','downstream_backlog')} for g in METHODS}
    secret=os.environ.get('DEEPSEEK_API_KEY');assert secret
    assert all(secret.encode() not in p.read_bytes() for parent in (SOURCE,FAILED) for p in parent.rglob('*') if p.is_file())
    EXPORT.mkdir();originals={};archives={}
    copy_and_hash(SOURCE,EXPORT,'development_v2',originals,archives);copy_and_hash(FAILED,EXPORT,'failed_v1_preflight',originals,archives)
    for version,parent in (('v2',SOURCE),('v1',FAILED)):
        for rel,h in read(parent/'freeze.json')['source_sha256'].items():
            target=EXPORT/'sources'/version/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target);assert digest(target)==h
            archives[target.relative_to(EXPORT).as_posix()]=digest(target)
    verification=dict(status='verified',episodes=240,node_periods=144000,pairs=40,normal_pre_notice_checks=160,
        pooled_new_minus_original=pooled,by_type=types,development_gate_passed=gate,absolute_shocked_means=absolute,
        api_http=len(all_calls),semantic_requests=semantic,token_usage=dict(usage),resources=resources,
        response_failure_types=dict(Counter(c.get('failure','unknown') for c in all_calls if c['status']!='valid')),
        schedules=schedules,runtime_failures=failures,source_input_model_training_hashes='passed',
        credential_absent=True,development_only=True,independent_confirmation=False,API_output_nondeterminism=True)
    (EXPORT/'verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8');archives['verification.json']=digest(EXPORT/'verification.json')
    (EXPORT/'export_hashes.json').write_text(json.dumps(dict(original_sha256=originals,archive_sha256=archives),indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in verification.items() if k!='schedules'},indent=2));print('ARCHIVE_VERIFIED',len(originals),len(archives))


if __name__=='__main__':main()
