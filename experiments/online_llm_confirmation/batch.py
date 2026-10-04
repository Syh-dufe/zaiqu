"""Preregister and execute independent confirmation using unchanged online core."""
import argparse
import csv
import importlib.util
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


core=load('confirmation_frozen_online_core',ROOT/'experiments/online_llm/run.py')
sys.path.insert(0,str(ROOT/'experiments/online_llm_artifacts'))
from archive import audit_run,usage
read,write,digest=core.read,core.write,core.digest
METHODS=core.METHODS
SEEDS=tuple(range(11,16))
ARCHIVE=ROOT/'docs/artifacts/online_llm_development_v1'
PROTOCOL=ROOT/'docs/superpowers/plans/2026-10-04-online-llm-confirmation.md'
RAW_TAG_NOTE=('Unchanged run.py emits development_only=True as a conservative technical tag. '
              'This wrapper preregisters independent confirmation before generation; child records '
              'are preserved exactly and their historical technical tag is not rewritten. '
              'No confirmation feedback is supplied to development or across episodes.')


def wrapper_hashes():
    paths=[Path(__file__),ROOT/'experiments/online_llm_artifacts/archive.py',
           ROOT/'experiments/formal_evaluation/analyze_multi.py',PROTOCOL]
    return {str(p.relative_to(ROOT)):digest(p) for p in paths}


def runtime_contract():
    import numpy as np
    import torch
    return dict(python_executable=sys.executable,python_version=sys.version,
                python_executable_sha256=digest(Path(sys.executable)),
                numpy_version=np.__version__,torch_version=torch.__version__)


def prior_inputs(exclude):
    used=set();sources=[]
    for parent in (ROOT/'results',ROOT/'docs/artifacts'):
        for path in parent.rglob('*.json'):
            if path.is_relative_to(exclude):
                continue
            try:
                data=read(path)
            except (ValueError,OSError):
                continue
            if not isinstance(data,dict):
                continue
            count=0
            for name in ('base','shock'):
                for trace in data.get(name,[]) if isinstance(data.get(name,[]),list) else []:
                    if isinstance(trace,list) and len(trace)>=200 and all(type(v) in (int,float) for v in trace[:200]):
                        used.add(tuple(trace[:200]));count+=1
            if count:
                sources.append(dict(path=str(path),sha256=digest(path),traces=count))
    return used,sources


def generate(ds,es):
    import numpy as np
    sys.path.insert(0,str(core.UPSTREAM))
    from envs.generator import merton
    np.random.seed(ds)
    base=[merton(200,20).demand_list for _ in range(4)]
    rng=random.Random(es)
    events=[dict(start_index=rng.randint(60,100),duration=rng.randint(20,40),intensity=intensity)
            for intensity in (1.25,1.25,1.5,1.5)]
    shock=[[min(20,math.ceil(event['intensity']*v)) if event['start_index']<=i<event['start_index']+event['duration'] else v
            for i,v in enumerate(trace)] for trace,event in zip(base,events)]
    return core.validate_inputs(dict(demand_seed=ds,event_seed=es,base=base,shock=shock,events=events))


def archive_contract():
    verification=read(ARCHIVE/'verification.json')
    assert verification['status']=='verified' and verification['episodes']==80
    for name,expected in read(ARCHIVE/'export_hashes.json')['archive_sha256'].items():
        assert digest(ARCHIVE/name)==expected,('development_archive_changed',name)
    return dict(archive=str(ARCHIVE),verification_sha256=digest(ARCHIVE/'verification.json'),
                manifest_sha256=digest(ARCHIVE/'manifest.json'),input_sha256=digest(ARCHIVE/'inputs.json'))


def register(out,library):
    if out.exists():
        raise RuntimeError('Registration path already exists')
    dev=read(ARCHIVE/'manifest.json')
    if core.source_hashes()!=dev['source_sha256'] or digest(library)!=dev['library_sha256']:
        raise RuntimeError('Frozen online mechanism or old library differs from development')
    if os.environ.get('DEEPSEEK_MODEL','deepseek-flash')!=dev['contracts']['11']['model']:
        raise RuntimeError('API model differs from frozen development mechanism')
    # Contracts and snapshots are frozen before creating any new test demand.
    frozen=dict(phase='independent_confirmation',development_only=False,raw_module_tag_note=RAW_TAG_NOTE,
        source_sha256=core.source_hashes(),wrapper_sha256=wrapper_hashes(),
        library_path=str(library),library_sha256=digest(library),development_archive=archive_contract(),
        reference_input_path=str(ARCHIVE/'inputs.json'),reference_input_sha256=digest(ARCHIVE/'inputs.json'),
        model_contracts={str(seed):core.contracts(ARCHIVE/'inputs.json',library,core.training(seed)) for seed in SEEDS},
        runtime=runtime_contract(),
        frozen_before_confirmation_input_generation=True,training_seeds=list(SEEDS),
        fixed_input_seed_pairs=[[20270901+2*i,20270902+2*i] for i in range(5)],
        api_model=os.environ.get('DEEPSEEK_MODEL','deepseek-flash'))
    out.mkdir(parents=True)
    write(out/'freeze.json',frozen)
    sources=out/'sources';sources.mkdir()
    for rel,expected in {**frozen['source_sha256'],**frozen['wrapper_sha256']}.items():
        target=sources/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target)
        assert digest(target)==expected
    shutil.copy2(library,out/'frozen_library.json')
    try:
        used,prior=prior_inputs(out)
        inputs=[generate(ds,es) for ds,es in frozen['fixed_input_seed_pairs']]
        base_signatures=[tuple(trace[:200]) for data in inputs for trace in data['base']]
        shock_signatures=[tuple(trace[:200]) for data in inputs for trace in data['shock']]
        collisions=[index for index,trace in enumerate(base_signatures) if trace in used]
        shock_collisions=[index for index,trace in enumerate(shock_signatures) if trace in used]
        cross_path_collisions=[(i,j) for i,trace in enumerate(shock_signatures)
            for j,other in enumerate(base_signatures) if i!=j and trace==other]
        duplicate_shocks=[(i,j) for i,trace in enumerate(shock_signatures)
            for j in range(i) if trace==shock_signatures[j]]
        if len(set(base_signatures))!=20 or collisions or shock_collisions or cross_path_collisions or duplicate_shocks:
            write(out/'collision_diagnosis.json',dict(inputs=inputs,historical_collision_indices=collisions,
                historical_shock_collision_indices=shock_collisions,cross_path_collisions=cross_path_collisions,
                duplicate_shock_pairs=duplicate_shocks,
                internal_unique_base_count=len(set(base_signatures)),no_resampling=True))
            raise RuntimeError('Fixed confirmation base demand collision; do not resample/drop cases')
        folder=out/'inputs';folder.mkdir()
        registered=[]
        for index,data in enumerate(inputs,1):
            path=folder/f'batch{index}.json';write(path,data)
            registered.append(dict(batch=index,path=str(path),sha256=digest(path),
                demand_seed=data['demand_seed'],event_seed=data['event_seed'],
                unchanged_shock_indices=[j for j,(base,shock) in enumerate(zip(data['base'],data['shock'])) if base[:200]==shock[:200]],
                contracts={str(seed):core.contracts(path,library,core.training(seed)) for seed in SEEDS}))
        write(out/'manifest.json',dict(status='registered',phase='independent_confirmation',development_only=False,
            raw_module_tag_note=RAW_TAG_NOTE,freeze_sha256=digest(out/'freeze.json'),
            methods=list(METHODS),training_seeds=list(SEEDS),trajectories=20,paired_shock_cases=100,
            episodes=1000,node_periods=600000,inputs=registered,prior_input_sources=prior,
            intensities_per_batch=[1.25,1.25,1.5,1.5],max_http_requests_batch=2000,
            max_semantic_requests=1000,max_http_per_episode=16,sequence='Serial5 models by5 batches',
            random_seed_rule='Unchanged20270803+100*local_trace+event1..4; localtrace resets in every4-trace batch',
            random_draws_repeat_across_batches=True,forecast_seeds_repeat_for_same_local_trace_and_period=True,
            primary_comparison=dict(reference='happo',method='online_feedback',endpoints=['cost','downstream_backlog'],
                bootstrap='Existing formal compare20000 crossed resamples; seed20261221',
                stronger_evidence='Both mean deltas and both97.5% upper bounds below0'),
            secondary_comparisons='All methods vsHAPPO; feedback vsold/once/random; descriptive95% intervals without whole-family claim',
            actual_uplift_strata=['zero','positive_below10percent','at_least10percent'],
            real_world_deadline_guaranteed=False,no_test_feedback_for_development=True,
            reset_episode_memory=True,all_fixed_cases_retained=True))
    except Exception as exc:
        write(out/'registration_failed.json',dict(failure=str(exc)[:1000],outputs_preserved=True));raise


def check_frozen(out,library):
    manifest=read(out/'manifest.json');frozen=read(out/'freeze.json')
    assert digest(out/'freeze.json')==manifest['freeze_sha256']
    assert runtime_contract()==frozen['runtime']
    assert core.source_hashes()==frozen['source_sha256'] and wrapper_hashes()==frozen['wrapper_sha256']
    assert digest(library)==frozen['library_sha256']==digest(out/'frozen_library.json')
    assert archive_contract()==frozen['development_archive']
    assert digest(Path(frozen['reference_input_path']))==frozen['reference_input_sha256']
    for rel,expected in {**frozen['source_sha256'],**frozen['wrapper_sha256']}.items():
        assert digest(out/'sources'/rel)==expected,('snapshot_changed',rel)
    for seed in SEEDS:
        assert core.contracts(Path(frozen['reference_input_path']),library,core.training(seed))==frozen['model_contracts'][str(seed)]
    for entry in manifest['inputs']:
        path=Path(entry['path']);assert digest(path)==entry['sha256'];core.validate_inputs(read(path))
        for seed in SEEDS:
            assert core.contracts(path,library,core.training(seed))==entry['contracts'][str(seed)]
    return manifest


def realized_shocks(manifest):
    output=[]
    for entry in manifest['inputs']:
        data=read(Path(entry['path']))
        for trace,event in enumerate(data['events']):
            start,end=event['start_index'],event['start_index']+event['duration']
            base_total=sum(data['base'][trace][start:end]);shock_total=sum(data['shock'][trace][start:end])
            uplift=(shock_total-base_total)/base_total if base_total else None
            if shock_total==base_total:
                stratum='zero'
            elif uplift is not None and uplift<.1:
                stratum='positive_below10percent'
            else:
                stratum='at_least10percent'
            output.append(dict(trajectory=(entry['batch']-1)*4+trace,batch=entry['batch'],local_trace=trace,
                intensity=event['intensity'],base_total=base_total,shock_total=shock_total,actual_uplift=uplift,
                stratum=stratum,clipped_periods=sum(event['intensity']*v>20 for v in data['base'][trace][start:end]),
                consumed_shock_equals_base=data['base'][trace][:200]==data['shock'][trace][:200]))
    return output


def partial_snapshot(out):
    fitness=[];requests=[];failures=[]
    for folder in sorted(out.glob('seed*_batch*')):
        if not folder.is_dir():
            continue
        if (folder/'episodes.json').exists():
            fitness.extend(dict(evaluation=folder.name,**r) for r in read(folder/'episodes.json'))
        if (folder/'calls.json').exists():
            requests.extend(dict(evaluation=folder.name,**r) for r in read(folder/'calls.json'))
        if (folder/'failed.json').exists():
            failures.append(dict(evaluation=folder.name,**read(folder/'failed.json')))
    write(out/'partial_summary.json',dict(phase='independent_confirmation',complete=False,
        complete_episodes_observed=len(fitness),fitness=fitness,api_requests=len(requests),
        api_failures=sum(r['status']!='valid' for r in requests),usage=usage(requests),failures=failures,
        no_cases_dropped=True,raw_module_tag_note=RAW_TAG_NOTE))


def analyze_complete(out,manifest):
    import numpy as np
    comparison_module=load('confirmation_formal_compare',ROOT/'experiments/formal_evaluation/analyze_multi.py')
    fitness=[];audits=[];calls=[];scores=[];runtime_failures=[];metrics=[]
    for seed in SEEDS:
        for entry in manifest['inputs']:
            batch=entry['batch'];folder=out/f'seed{seed}_batch{batch}'
            audit=audit_run(folder,read(Path(entry['path'])),entry['contracts'][str(seed)],allow_runtime_fallbacks=True)
            fitness.extend(dict(e,trajectory=(batch-1)*4+e['trace'],batch=batch) for e in audit['records'])
            audits.append(dict(seed=seed,batch=batch,**{k:v for k,v in audit.items() if k!='records'}))
            calls.extend(dict(seed=seed,batch=batch,**r) for r in read(folder/'calls.json'))
            scores.extend(dict(seed=seed,batch=batch,**r) for r in read(folder/'scores.json'))
            runtime_failures.extend(dict(seed=seed,batch=batch,**r) for r in read(folder/'runtime_failures.json'))
            with (folder/'periods.csv').open(encoding='utf-8',newline='') as stream:
                grouped={}
                for row in csv.DictReader(stream):
                    if row['scenario']=='shock':
                        grouped.setdefault((row['group'],int(row['trace'])),[]).append(row)
            demands=read(Path(entry['path']))
            for (group,trace),rows in grouped.items():
                event=demands['events'][trace];notification=event['start_index']+3
                downstream=[r for r in rows if r['node']=='0']
                end=event['start_index']+event['duration']+1;recovery=None
                for i in range(196):
                    if int(downstream[i]['period'])>=end and all(float(r['backlog'])==0 for r in downstream[i:i+5]):
                        recovery=int(downstream[i]['period'])-end;break
                metrics.append(dict(seed=seed,trajectory=(batch-1)*4+trace,group=group,
                    backlog_after_notification={str(h):sum(float(r['backlog']) for r in downstream if notification<=int(r['period'])<notification+h) for h in (10,20)},
                    peak_post_start_backlog=max(float(r['backlog']) for r in downstream if int(r['period'])>=event['start_index']+1),
                    recovery_periods=recovery,recovery_censored=recovery is None,
                    tail_inventory=[int(r['inventory']) for r in rows if int(r['period'])==200]))
    expected={(seed,group,scenario,trace) for seed in SEEDS for group in METHODS for scenario in ('base','shock') for trace in range(20)}
    assert len(fitness)==1000 and {(e['seed'],e['group'],e['scenario'],e['trajectory']) for e in fitness}==expected
    assert sum(a['raw_rows'] for a in audits)==600000
    lookup={(e['seed'],e['group'],e['scenario'],e['trajectory']):e for e in fitness}
    def matrix(group):
        return np.asarray([[ [lookup[seed,group,'shock',trace]['cost'],lookup[seed,group,'shock',trace]['downstream_backlog']]
            for trace in range(20)] for seed in SEEDS])
    primary=comparison_module.compare(matrix('happo'),matrix('online_feedback'))
    secondary={}
    comparisons=[('happo',g) for g in METHODS[1:]]+[('llm_library','online_feedback'),('online_once','online_feedback'),('random_screen','online_feedback')]
    for reference,method in comparisons:
        result=comparison_module.compare(matrix(reference),matrix(method))
        if (reference,method)==('happo','online_feedback'):
            continue
        result.pop('stronger_evidence');result.pop('ci97p5')
        secondary[f'{method}_vs_{reference}']=dict(result,descriptive_only=True,whole_family_corrected=False)
    shocks=realized_shocks(manifest);paired=[];per_model=[];strata=[]
    for reference,method in comparisons:
        delta=matrix(method)-matrix(reference)
        for i,seed in enumerate(SEEDS):
            per_model.append(dict(seed=seed,reference=reference,method=method,mean_delta=delta[i].mean(axis=0).tolist()))
            for trace in range(20):
                paired.append(dict(seed=seed,trajectory=trace,reference=reference,method=method,
                    cost_delta=float(delta[i,trace,0]),backlog_delta=float(delta[i,trace,1])))
        for stratum in manifest['actual_uplift_strata']:
            indices=[s['trajectory'] for s in shocks if s['stratum']==stratum]
            strata.append(dict(stratum=stratum,reference=reference,method=method,trajectories=indices,
                paired_cases=5*len(indices),mean_delta=delta[:,indices].mean(axis=(0,1)).tolist() if indices else None,
                descriptive_only=True,no_exclusion_or_selection=True))
    summary=dict(phase='independent_confirmation',development_only=False,complete=True,
        raw_module_tag_note=RAW_TAG_NOTE,episodes=1000,node_periods=600000,primary=primary,secondary=secondary,
        fitness=fitness,paired_deltas=paired,per_model=per_model,
        all_unfavorable_pairs=[r for r in paired if r['cost_delta']>0 or r['backlog_delta']>0],
        realized_shocks=shocks,uplift_strata=strata,episode_metrics=metrics,audits=audits,
        api_requests=len(calls),api_failures=sum(c['status']!='valid' for c in calls),usage=usage(calls),
        api_seconds=sum(c.get('seconds',0) for c in calls),evaluation_wall_seconds=sum(a['wall_seconds'] for a in audits),
        screening_seconds=sum(a['screening_seconds'] for a in audits),runtime_failures=runtime_failures,
        selection_events=sum(a['selection_events'] for a in audits),accepted_selections=sum(s.get('chosen')!='zero' for s in scores),
        changed_node_orders=sum(a['changed_node_orders'] for a in audits),currency_cost=None,
        real_world_deadline_guaranteed=False,random_draws_repeat_across_batches=True,
        recovery_definition='First5 consecutive zero downstream backlog after actual shock end; absence censored',
        claim_limit='Primary overall effect alone does not establish disaster-specific adaptation; secondary comparisons descriptive and LLM attribution requires separate support')
    assert len(calls)<=manifest['max_http_requests_batch']
    assert sum(c['attempt']==1 for c in calls)<=manifest['max_semantic_requests']
    write(out/'summary.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/online_llm/confirmation_v1')
    parser.add_argument('--operator-library',type=Path,default=core.LIBRARY)
    parser.add_argument('--preflight',action='store_true',help='Freeze/register/check only; no API or environment evaluation')
    opts=parser.parse_args();out=opts.output.resolve();library=opts.operator_library.resolve()
    if not os.environ.get('DEEPSEEK_API_KEY'):
        raise RuntimeError('DEEPSEEK_API_KEY missing')
    if not out.exists():
        register(out,library)
    if not (out/'manifest.json').exists() or (out/'registration_failed.json').exists():
        raise RuntimeError('Incomplete/failed registration; preserve outputs and inspect')
    if any((out/name).exists() for name in ('launch.json','failed.json','completed.json')):
        raise RuntimeError('Confirmation already launched or failed; refuse repeated launch')
    manifest=check_frozen(out,library)
    if opts.preflight:
        print('CONFIRMATION_PREFLIGHT_OK noAPI/evaluation',str(out),'1000 episodes registered',flush=True);return
    with (out/'launch.json').open('x',encoding='utf-8') as stream:
        import json
        json.dump(dict(pid=os.getpid(),started=time.time(),manifest_sha256=digest(out/'manifest.json'),phase='independent_confirmation'),stream,indent=2)
    completed=[]
    try:
        for seed in SEEDS:
            for entry in manifest['inputs']:
                check_frozen(out,library)
                batch=entry['batch'];label=f'seed{seed}_batch{batch}'
                write(out/'progress.json',dict(status='evaluating',seed=seed,batch=batch,pid=os.getpid(),completed=completed))
                command=[sys.executable,'-u',str(ROOT/'experiments/online_llm/run.py'),'--run-name',label,
                    '--input-file',entry['path'],'--training-directory',str(core.training(seed)),
                    '--operator-library',str(library),'--output-root',str(out)]
                with (out/f'{label}.log').open('x',encoding='utf-8') as stream:
                    process=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
                if process.returncode:
                    raise RuntimeError(f'{label} failed; retained log/API/partial episodes')
                check_frozen(out,library)
                audit=audit_run(out/label,read(Path(entry['path'])),entry['contracts'][str(seed)],allow_runtime_fallbacks=True)
                completed.append(dict(seed=seed,batch=batch,path=str(out/label),input_sha256=entry['sha256'],
                    protocol_sha256=digest(out/label/'protocol.json'),api_requests=audit['api_requests'],episodes=40))
                write(out/'progress.json',dict(status='between_batches',pid=os.getpid(),completed=completed))
        summary=analyze_complete(out,manifest);check_frozen(out,library)
        write(out/'completed.json',dict(status='completed',phase='independent_confirmation',development_only=False,
            episodes=1000,node_periods=600000,api_requests=summary['api_requests'],
            primary=summary['primary'],summary_sha256=digest(out/'summary.json'),all_cases_retained=True))
        write(out/'progress.json',dict(status='completed',pid=os.getpid(),completed=completed))
        print('CONFIRMATION_COMPLETED',flush=True)
    except Exception as exc:
        write(out/'failed.json',dict(failure=type(exc).__name__,detail=str(exc)[:1000],completed=completed,outputs_preserved=True))
        try:
            partial_snapshot(out)
        except Exception as error:
            write(out/'analysis_failed.json',dict(failure=str(error)[:1000]))
        raise


if __name__=='__main__':
    main()
