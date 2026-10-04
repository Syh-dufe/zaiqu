"""Raw causal, model, format, replacement and execution development audits."""
import argparse
import ast
import csv
import importlib.util
import inspect
import json
import math
from pathlib import Path
import statistics
import sys

if 'case_only_run_core' in sys.modules:
    CORE=sys.modules['case_only_run_core']
    if Path(CORE.__file__).resolve()!=Path(__file__).with_name('run.py').resolve():
        raise RuntimeError('Case-only run alias collision')
else:
    spec=importlib.util.spec_from_file_location('case_only_run_core',Path(__file__).with_name('run.py'))
    CORE=importlib.util.module_from_spec(spec);sys.modules[spec.name]=CORE;spec.loader.exec_module(CORE)
read,write,digest=CORE.read,CORE.write,CORE.digest
from shadow import eligible


def forbidden(value):
    if isinstance(value,dict):
        assert not {'intensity','duration','start_index','validation_zero','validation_candidate','review_feedback'}&value.keys()
        for child in value.values():
            forbidden(child)
    elif isinstance(value,list):
        for child in value:
            forbidden(child)


def best_eligible(scores):
    choices=[s for s in scores[1:] if eligible(s,scores[0])]
    return min((s['cost'] for s in choices),default=None)


def usage(calls):
    result={}
    for call in calls:
        for key,value in (call.get('usage') or {}).items():
            if isinstance(value,(int,float)):
                result[key]=result.get(key,0)+value
    return result


def audit_normalization(folder,calls):
    records=read(folder/'normalization_audit.json');expected=[]
    for call in calls:
        if call['group']!='case_feedback':
            continue
        # Reconstruct the original comprehension: only completed JSON with the
        # right candidate count reaches compilation; stop at the first error.
        try:
            choice=call['response']['choices'][0]
            if choice['finish_reason']!='stop':
                continue
            values=json.loads(choice['message']['content'])['candidates']
            count=json.loads(call['request']['messages'][1]['content'])['candidate_count']
            if not isinstance(values,list) or len(values)!=count:
                continue
        except (KeyError,IndexError,TypeError,ValueError):
            continue
        for value in values:
            identity={k:call[k] for k in ('group','scenario','trace','decision_period','event','stage','attempt')}
            item=dict(**identity,index=len(expected),raw_candidate_sha256=CORE.CLIENT.canonical_hash(value),changes=[])
            try:
                normalized,changes=CORE.CLIENT.normalize_candidate(value,item['changes'])
                item['normalized_candidate_sha256']=CORE.CLIENT.canonical_hash(normalized)
                compiled=CORE.CLIENT.ORIGINAL_COMPILE(normalized)
                item.update(status='valid',compiled_ast=[[ast.dump(a),ast.dump(b)] for a,b in compiled])
            except Exception as exc:
                item.update(status='failed',failure_type=type(exc).__name__,failure=str(exc)[:400])
            item.update(normalization_used=bool(item['changes']),replaced_tokens=sum(len(c['edits']) for c in item['changes']))
            expected.append(item)
            if item['status']=='failed':
                break
    assert len(records)==len(expected)
    for actual,item in zip(records,expected):
        assert {k:v for k,v in actual.items() if k!='seconds'}==item
        assert isinstance(actual['seconds'],(int,float)) and actual['seconds']>=0
    return dict(compilations=len(records),candidates_normalized=sum(r['normalization_used'] for r in records),
        valid_normalized=sum(r['normalization_used'] and r['status']=='valid' for r in records),
        replaced_boolean_tokens=sum(r['replaced_tokens'] for r in records),
        remaining_syntax_failures=sum(r.get('failure_type') in ('SyntaxError','IndentationError','TokenError') for r in records),
        remaining_compile_failures=sum(r['status']=='failed' for r in records),
        normalization_compile_seconds=sum(r['seconds'] for r in records),raw_candidate_and_span_audit='passed')


def audit_run(folder,demands,contract):
    done=read(folder/'completed.json');protocol=read(folder/'protocol.json')
    assert done['episodes']==24 and done['rows']==14400 and done['training_updates']==0
    assert done['runtime_failures']==read(folder/'runtime_failures.json')
    for key,value in contract.items():
        assert protocol[key]==value,('child_contract',key)
    assert protocol['system']==CORE.SYSTEM and protocol['systems_by_method']==CORE.SYSTEMS
    assert CORE.SYSTEMS['online_feedback']==CORE.SYSTEMS['case_feedback']==CORE.BASE.SYSTEM
    assert inspect.getsource(CORE.CLIENT.V1Client.generate)==inspect.getsource(CORE.CLIENT.CaseClient.generate)
    assert CORE.CLIENT.BASELINE is not CORE.CLIENT.COMPAT
    assert CORE.CLIENT.BASELINE.compile_rule is CORE.CLIENT.ORIGINAL_COMPILE
    assert CORE.CLIENT.COMPAT.compile_rule is CORE.CLIENT.compile_rule
    # Direct original class source reuse is stronger evidence than copied bodies.
    assert Path(inspect.getsourcefile(CORE.CLIENT.V1Client)).resolve()==CORE.ROOT/'experiments/online_llm/client.py'
    assert Path(inspect.getsourcefile(CORE.CONTROL.V1Controller)).resolve()==CORE.ROOT/'experiments/online_llm/controller.py'
    assert set(done['parameter_checks'])==set(CORE.METHODS)
    assert all(c['unchanged'] and c['before']==c['after']==contract['expected_parameter_sha256'] for c in done['parameter_checks'].values())
    assert read(folder/'demands.json')==demands
    with (folder/'periods.csv').open(encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    assert len(rows)==14400;grouped={}
    for row in rows:
        assert float(row['cost'])==int(row['inventory'])+int(row['backlog']) and 0<=int(row['actual_order'])<=20
        grouped.setdefault((row['group'],row['scenario'],int(row['trace'])),[]).append(row)
    episodes=read(folder/'episodes.json')
    assert len(episodes)==24 and set(grouped)=={(g,s,t) for g in CORE.METHODS for s in ('base','shock') for t in range(4)}
    for episode in episodes:
        local=grouped[episode['group'],episode['scenario'],episode['trace']]
        assert len(local)==600 and {(int(r['period']),int(r['node'])) for r in local}=={(p,n) for p in range(1,201) for n in range(3)}
        assert math.isclose(statistics.mean(float(r['cost']) for r in local),episode['cost'],abs_tol=1e-9)
        assert math.isclose(statistics.mean(int(r['backlog']) for r in local if r['node']=='0'),episode['downstream_backlog'],abs_tol=1e-9)
        assert episode['generation_events']==(4 if episode['scenario']=='shock' and episode['group']!='happo' else 0)
    keys=('period','node','cost','inventory','backlog','actual_order')
    for trace in range(4):
        for scenario in ('base','shock'):
            end=201 if scenario=='base' else demands['events'][trace]['start_index']+3
            baseline=[tuple(r[k] for k in keys) for r in grouped['happo',scenario,trace] if int(r['period'])<end]
            for group in CORE.METHODS[1:]:
                assert baseline==[tuple(r[k] for k in keys) for r in grouped[group,scenario,trace] if int(r['period'])<end]
    information=read(folder/'information_audits.json');assert len(information)==4800
    infos={}
    for item in information:
        p=item['decision_period']-1;through=p//3*3;trace=demands[item['scenario']][item['trace']]
        assert item['observed_periods']==p and item['delivered_through_period']==through and item['report_age']==p-through
        assert item['reconstructed_history']==[sum(trace[i:i+3])/3 for i in range(0,through,3) for _ in range(3)]
        infos[item['group'],item['scenario'],item['trace'],p+1]=item
    assert len(infos)==4800
    reports=read(folder/'delivered_reports.json');assert len(reports)==24*66
    for report in reports:
        end=report['end_period'];trace=demands[report['scenario']][report['trace']]
        assert end%3==0 and report['start_period']==end-2 and report['available_from_decision_period']==end+1 and report['delivered_after_period']==end
        assert report['demand_total']==sum(trace[end-3:end]) and report['demand_mean']==sum(trace[end-3:end])/3
    calls=read(folder/'calls.json');assert len(calls)==done['calls'] and len(calls)<=128
    per_episode={};semantic={}
    for call in calls:
        assert call['group'] in CORE.METHODS[1:] and call['scenario']=='shock' and 1<=call['event']<=4
        assert call['attempt'] in (1,2) and call['stage'] in ('initial','revision')
        key=(call['group'],call['trace']);per_episode[key]=per_episode.get(key,0)+1
        semantic.setdefault((*key,call['event'],call['stage']),[]).append(call)
        expected_system=CORE.SYSTEMS[call['group']]
        assert call['request']['messages'][0]['content']==expected_system and call['request']['model']==contract['model']
        request=call['request']
        assert request['response_format']=={'type':'json_object'} and request['thinking']=={'type':'disabled'}
        assert request['temperature']==.2 and request['max_tokens']==3000
        messages=request['messages']
        assert messages[0]['role']=='system' and messages[1]['role']=='user'
        assert len(messages)==(2 if call['attempt']==1 else 4)
        if call['attempt']==2:
            assert messages[2]['role']=='assistant' and messages[3]['role']=='user'
        context=json.loads(messages[1]['content']);forbidden(context)
        assert not {'retained_previous_execution','protected_candidate_id','replacement_target_id'} & context.keys()
        info=infos[call['group'],call['scenario'],call['trace'],call['decision_period']]
        assert context['nodes']==info['rule_features'] and context['observed_periods']==call['decision_period']-1
        assert context['available_report']=={k:info[k] for k in ('interval','observed_periods','delivered_through_period','report_age','reconstructed_history','latest_report')}
        memory=context['last_two_events'];assert len(memory)==min(2,call['event']-1)
        assert all(m['event']<call['event'] and m['observed_periods']<context['observed_periods'] for m in memory)
        if call['stage']=='revision':
            assert context['candidate_count']==1 and len(context['search_feedback'])==4
        else:
            assert context['candidate_count']==3
        if call['status']=='valid':
            compiler=CORE.CLIENT.ORIGINAL_COMPILE if call['group']=='online_feedback' else CORE.CLIENT.compile_rule
            assert len(call['candidates'])==context['candidate_count']
            for candidate in call['candidates']:
                compiler(candidate)
    for attempts in semantic.values():
        assert [c['attempt'] for c in attempts] in ([1],[1,2])
        if len(attempts)==2:
            first,repair=attempts
            assert first['status']=='failed' and first['failure_kind']=='format'
            assert repair['request']['messages'][:2]==first['request']['messages']
            choice=(first.get('response',{}).get('choices') or [{}])[0]
            assert repair['request']['messages'][2]['content']==choice.get('message',{}).get('content',first['raw_response'])
            count=json.loads(first['request']['messages'][1]['content'])['candidate_count']
            expected_repair='Repair the JSON/DSL format only. '+first['failure']+f' Return exactly {count} candidates with valid expressions. Use True for an unconditional predicate.'
            assert repair['request']['messages'][3]['content']==expected_repair
    for episode in episodes:
        count=per_episode.get((episode['group'],episode['trace']),0) if episode['scenario']=='shock' else 0
        assert episode['episode_http']==count<=16
    normalization=audit_normalization(folder,calls)
    scores=read(folder/'scores.json');generation={};revision_metrics=[]
    for result in scores:
        assert result['scenario']=='shock' and result['group']!='happo'
        if result.get('screening_event') is False:
            assert result['execution_failure'] and result['chosen']=='zero';continue
        assert result['method']==result['group']
        info=infos[result['group'],result['scenario'],result['trace'],result['decision_period']]
        expected_paths=CORE.CONTROL.ORIGINAL.forecasts(info['reconstructed_history'],result['trace'],
            result['decision_period']-1,'merton',info['report_age'])
        assert result['forecasts']==[expected_paths[0],expected_paths[1]]
        assert result['decision_period']>=demands['events'][result['trace']]['start_index']+3
        assert (result['decision_period']-(demands['events'][result['trace']]['start_index']+3))%5==0
        assert len(result['forecasts'])==2 and all(len(paths)==3 for paths in result['forecasts'])
        assert all(len(path)==min(20,201-result['decision_period']) for paths in result['forecasts'] for path in paths)
        search=result['search'];assert len(search)==4 and search[0]['id']=='zero' and search[0]['valid']
        candidates=[s for s in search[1:] if eligible(s,search[0])]
        expected=min(candidates,key=lambda c:c['cost'])['id'] if candidates else 'zero'
        assert result['validation_candidate']['id']==expected
        if expected!='zero' and not eligible(result['validation_candidate'],result['validation_zero']):
            expected='zero'
        if result.get('execution_failure'):
            assert result['selected_before_execution']==expected
        assert result['chosen']==('zero' if result.get('execution_failure') else expected)
        if not result.get('generation_event'):
            continue
        generation.setdefault((result['group'],result['trace']),[]).append(result)
        assert len(result['candidates'])==4 and len(result['search_revision_feedback'])==4
        before=result['search_revision_feedback'];initial_best=best_eligible(before);final_best=best_eligible(search)
        revision_metrics.append(dict(group=result['group'],trace=result['trace'],event=result['event'],
            initial_best_eligible_cost=initial_best,final_best_eligible_cost=final_best,
            best_eligible_lost=initial_best is not None and (final_best is None or final_best>initial_best+1e-9),
            initial_eligible_count=sum(eligible(s,before[0]) for s in before[1:]),final_eligible_count=len(candidates),
            generation_failed=bool(result.get('failure')),revision_failed=result.get('revision_failed',False)))
        assert result['method']==result['group']
        assert not {'initial_candidates','retained_candidate_id','retained_execution','protected_candidate_id',
                    'replacement_target_id','fresh_candidate_count'} & result.keys()
        assert not {'retained_previous_execution','protected_candidate_id','replacement_target_id'} & result['context'].keys()
        # Original candidate index0 is the only replacement slot. Initial
        # candidate rules are available in the logged revision request.
        semantic_initial=semantic[result['group'],result['trace'],result['event'],'initial']
        valid_initial=next((c for c in semantic_initial if c['status']=='valid'),None)
        initial_ids=[s['id'] for s in before]
        if valid_initial:
            initial_rules=valid_initial['candidates']
            original=[dict(id=initial_ids[i+1],rule=r) for i,r in enumerate(initial_rules)]
            revisions=semantic.get((result['group'],result['trace'],result['event'],'revision'),[])
            assert revisions
            revision_context=json.loads(revisions[0]['request']['messages'][1]['content'])
            assert revision_context['previous_candidates']==original
            assert revision_context['search_feedback']==before
            assert revision_context['revision_instruction']=='Return one replacement candidate; it will replace candidate index0. Review results are unavailable.'
            replacement=next((c for c in revisions if c['status']=='valid'),None)
            expected_final=[dict(id='zero',rule=None)]+original
            if replacement:
                expected_final[1]=dict(id=f"event{result['event']}_revision_0",rule=replacement['candidates'][0])
            assert result['candidates']==expected_final
            assert bool(result['revision_failed'])==(replacement is None)
        else:
            assert result['failure']=='generation_failed'
            assert (result['group'],result['trace'],result['event'],'revision') not in semantic
            assert [c['id'] for c in result['candidates']]==initial_ids==['zero','fallback_0','fallback_1','fallback_2']
            assert result['candidates']==[dict(id='zero',rule=None)]+[
                dict(id=f'fallback_{i}',rule={'rules':[{'when':'True','delta':'0'}]}) for i in range(3)]
    for trace in range(4):
        periods=[[r['decision_period'] for r in generation[g,trace]] for g in CORE.METHODS[1:]]
        expected=[demands['events'][trace]['start_index']+3+5*i for i in range(4)]
        assert len(periods[0])==4 and all(p==expected for p in periods)
    execution_counts=[]
    for group in CORE.METHODS[1:]:
        local=[r for r in rows if r['group']==group and r['scenario']=='shock']
        changed=[r for r in local if r['actual_order']!=r['happo_order']]
        execution_counts.append(dict(group=group,changed_node_orders=len(changed),
            changed_decision_periods=len({(int(r['trace']),int(r['period'])) for r in changed})))
    return dict(seed=contract['training_seed'],episodes=len(episodes),node_periods=len(rows),
        revision_metrics=revision_metrics,execution_counts=execution_counts,normalization=normalization,
        normal_action_changes=sum(r['actual_order']!=r['happo_order'] for r in rows if r['scenario']=='base'),
        changed_node_orders=sum(r['actual_order']!=r['happo_order'] for r in rows),
        raw_file_sha256={name:digest(folder/name) for name in ('protocol.json','demands.json','calls.json','periods.csv','episodes.json','scores.json','information_audits.json','delivered_reports.json','normalization_audit.json','runtime_failures.json','completed.json')},
        source_model_raw_cost_report_prompt_budget_replacement_and_execution_audit='passed')


def analyze(out,require_complete=False):
    manifest=read(out/'manifest.json');fitness=[];calls=[];scores=[];audits=[];failures=[]
    for seed in (11,12):
        folder=out/f'seed{seed}'
        if not folder.exists():
            failures.append(dict(seed=seed,status='not_started'));continue
        if (folder/'completed.json').exists():
            audits.append(audit_run(folder,read(out/'inputs.json'),manifest['contracts'][str(seed)]))
        if (folder/'episodes.json').exists():
            fitness.extend(dict(seed=seed,**e) for e in read(folder/'episodes.json'))
        if (folder/'calls.json').exists():
            calls.extend(dict(seed=seed,**c) for c in read(folder/'calls.json'))
        if (folder/'scores.json').exists():
            scores.extend(dict(seed=seed,**s) for s in read(folder/'scores.json'))
        for name in ('failed.json','runtime_failures.json'):
            if (folder/name).exists():
                data=read(folder/name);failures.extend(dict(seed=seed,**r) for r in (data if isinstance(data,list) else [data]))
    paired=[];per_model=[];comparisons=[]
    for reference,method in [('happo',g) for g in CORE.METHODS[1:]]+[('online_feedback','case_feedback')]:
        local=[]
        for seed in (11,12):
            model=[]
            for trace in range(4):
                pair=[next((e for e in fitness if e['seed']==seed and e['trace']==trace and e['scenario']=='shock' and e['group']==g),None) for g in (reference,method)]
                if all(pair):
                    row=dict(seed=seed,trace=trace,reference=reference,method=method,
                        cost_delta=pair[1]['cost']-pair[0]['cost'],backlog_delta=pair[1]['downstream_backlog']-pair[0]['downstream_backlog'])
                    paired.append(row);local.append(row);model.append(row)
            per_model.append(dict(seed=seed,reference=reference,method=method,pairs=len(model),
                mean_cost_delta=statistics.mean(r['cost_delta'] for r in model) if model else None,
                mean_backlog_delta=statistics.mean(r['backlog_delta'] for r in model) if model else None))
        comparisons.append(dict(reference=reference,method=method,pairs=len(local),descriptive_development_only=True,
            mean_cost_delta=statistics.mean(r['cost_delta'] for r in local) if local else None,
            mean_backlog_delta=statistics.mean(r['backlog_delta'] for r in local) if local else None,
            cost_improved=sum(r['cost_delta']<0 for r in local),cost_worsened=sum(r['cost_delta']>0 for r in local),
            backlog_improved=sum(r['backlog_delta']<0 for r in local),backlog_worsened=sum(r['backlog_delta']>0 for r in local)))
    revision=[dict(seed=a['seed'],**r) for a in audits for r in a['revision_metrics']]
    method_diagnostics=[]
    for group in CORE.METHODS[1:]:
        cs=[c for c in calls if c['group']==group];rs=[r for r in revision if r['group']==group]
        selections=[s for s in scores if s['group']==group and s.get('screening_event') is not False]
        method_diagnostics.append(dict(group=group,http_requests=len(cs),failed_http=sum(c['status']!='valid' for c in cs),
            format_failures=sum(c.get('failure_kind')=='format' for c in cs),
            transport_failures=sum(c.get('failure_kind')=='transport' for c in cs),
            http_failures=sum(c.get('failure_kind')=='http' for c in cs),
            execution_failures=sum(f.get('group')==group for f in failures),usage=usage(cs),api_seconds=sum(c.get('seconds',0) for c in cs),
            generation_events=len(rs),generation_failures=sum(r['generation_failed'] for r in rs),revision_failures=sum(r['revision_failed'] for r in rs),
            eligible_best_losses=sum(r['best_eligible_lost'] for r in rs),selection_events=len(selections),
            accepted_selections=sum(s['chosen']!='zero' for s in selections),
            screening_seconds=sum(s.get('seconds',0)+s.get('revision_scoring_seconds',0) for s in selections)))
    eligible_development=[c['method'] for c in comparisons if c['reference']=='online_feedback' and c['pairs']==8 and c['mean_cost_delta']<0 and c['mean_backlog_delta']<=0]
    data=read(out/'inputs.json')
    realized=[]
    for trace,event in enumerate(data['events']):
        start,end=event['start_index'],event['start_index']+event['duration']
        base_total=sum(data['base'][trace][start:end]);shock_total=sum(data['shock'][trace][start:end])
        realized.append(dict(trace=trace,intensity=event['intensity'],base_total=base_total,shock_total=shock_total,
            actual_uplift=(shock_total-base_total)/base_total if base_total else None,
            clipped_periods=sum(event['intensity']*v>20 for v in data['base'][trace][start:end]),
            unchanged=data['base'][trace][:200]==data['shock'][trace][:200]))
    if require_complete:
        assert len(fitness)==48 and len(audits)==2 and sum(a['node_periods'] for a in audits)==28800
        assert {(e['seed'],e['group'],e['scenario'],e['trace']) for e in fitness}=={(seed,g,s,t) for seed in (11,12) for g in CORE.METHODS for s in ('base','shock') for t in range(4)}
    assert len(calls)<=256
    summary=dict(development_only=True,complete=require_complete,episodes_observed=len(fitness),expected_episodes=48,
        fitness=fitness,paired_deltas=paired,comparisons=comparisons,per_model=per_model,
        all_unfavorable_pairs=[r for r in paired if r['cost_delta']>0 or r['backlog_delta']>0],
        audits=audits,failures=failures,revision_metrics=revision,method_diagnostics=method_diagnostics,
        normalization_by_model=[dict(seed=a['seed'],**a['normalization']) for a in audits],
        normal_action_changes=sum(a['normal_action_changes'] for a in audits),
        realized_shocks=realized,api_requests=len(calls),api_failures=sum(c['status']!='valid' for c in calls),usage=usage(calls),
        eligible_for_development_consideration=eligible_development,
        claim_limit='Eight crossed development pairs on reused neutral v3 inputs; independent API draws are stochastic and not identical generated outputs; new independent test required for deployed version; no automatic adoption',
        revision_metrics_note='Search predictions only; syntax and replacement audits do not establish realized performance',currency_cost=None)
    write(out/'summary.json',summary);return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);parser.add_argument('--complete',action='store_true')
    options=parser.parse_args();analyze(options.output.resolve(),options.complete)
