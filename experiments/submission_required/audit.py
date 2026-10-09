"""Independent raw-node-period, information, method and budget audit."""
import csv
import math
from pathlib import Path
from common import read,write,digest

def audit(directory,methods,data,expected_hash,offline=False):
    directory=Path(directory);done=read(directory/'completed.json')
    episodes=read(directory/'episodes.json');calls=read(directory/'calls.json')
    scores=read(directory/'scores.json');info=read(directory/'information_audits.json');deliveries=read(directory/'delivered_reports.json')
    with (directory/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    expected={(m,s,t,p,n) for m in methods for s in ('base','shock') for t in range(4) for p in range(1,201) for n in range(3)}
    keyed={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in rows}
    assert len(rows)==len(keyed)==len(expected) and set(keyed)==expected
    assert done['rows']==len(rows) and done['episodes']==len(methods)*8 and done['training_updates']==0
    assert len(episodes)==len(methods)*8 and len({(e['group'],e['scenario'],e['trace']) for e in episodes})==len(episodes)
    assert set(done['parameter_checks'])==set(methods)
    for check in done['parameter_checks'].values():assert check['before']==check['after']==expected_hash and check['unchanged']
    infos={(r['group'],r['scenario'],r['trace'],r['decision_period']):r for r in info}
    assert len(info)==len(infos)==len(methods)*1600
    changed={m:0 for m in methods};decision_count={m:0 for m in methods}
    for (m,s,t,p,n),r in keyed.items():
        assert int(r['demand'])==data[s][t][p-1]
        assert float(r['cost'])==int(r['inventory'])+int(r['backlog'])
        assert 0<=int(r['actual_order'])<=20 and 0<=int(r['policy_order'])<=20
        notice=data['events'][t]['start_index']+3
        assert r['notification_period']==(str(notice) if s=='shock' and p>=notice else '')
        if m=='happo' or s=='base' or p<notice:assert r['actual_order']==r['policy_order'] and r['chosen']=='zero'
        if n==0:
            i=infos[m,s,t,p];assert i['observed_periods']==p-1 and i['delivered_through_period']==(p-1)//3*3
            assert i['reconstructed_history']==[v for report in deliveries
                if report['group']==m and report['scenario']==s and report['trace']==t and report['available_from_decision_period']<=p
                for v in [report['demand_mean']]*3]
            if s=='shock':
                decision_count[m]+=1
                changed[m]+=any(keyed[m,s,t,p,node]['actual_order']!=keyed[m,s,t,p,node]['policy_order'] for node in range(3))
    for e in episodes:
        m,s,t=e['group'],e['scenario'],e['trace']
        subset=[keyed[m,s,t,p,n] for p in range(1,201) for n in range(3)]
        assert math.isclose(e['cost'],sum(float(x['cost']) for x in subset)/600,abs_tol=1e-9)
        assert math.isclose(e['downstream_backlog'],sum(int(x['backlog']) for x in subset if int(x['node'])==0)/200,abs_tol=1e-9)
        if m in ('happo','deterministic_search') or s=='base':assert e['episode_http']==0
        assert e['generation_events']<=(1 if m=='first_only' else 4) and e['episode_http']<=16
        c=[x for x in calls if x['group']==m and x['scenario']==s and x['trace']==t]
        assert len(c)==e['episode_http']
        if m=='no_feedback':assert all(x['stage']=='initial' for x in c)
        for p in range(1,data['events'][t]['start_index']+1):
            for n in range(3):
                left,right=keyed[m,'base',t,p,n],keyed[m,'shock',t,p,n]
                assert all(left[k]==right[k] for k in ('cost','inventory','backlog','policy_order','actual_order'))
        if 'happo' in methods:
            for scenario in ('base','shock'):
                end=201 if scenario=='base' else data['events'][t]['start_index']+3
                for p in range(1,end):
                    for n in range(3):
                        assert all(keyed[m,scenario,t,p,n][k]==keyed['happo',scenario,t,p,n][k] for k in ('cost','actual_order','policy_order'))
    assert all(c['group'] in ('online_feedback','no_feedback','no_review','first_only') and c['scenario']=='shock' for c in calls)
    for s in scores:
        m=s['group'];t=s['trace'];p=s['decision_period']
        if s.get('execution_failure'):continue
        assert s['scenario']=='shock' and (p-data['events'][t]['start_index']-3)%5==0
        assert all(x['valid'] for x in s['search'][:1])
        if m=='no_review':assert s['validation_zero'] is None and s['validation_candidate'] is None and s['review'] is False
        if s.get('generation_event'):
            assert len(s['candidates'])==4
            context=s['context'];assert 'search_feedback' not in context and 'validation_candidate' not in context
            assert context['available_report']['observed_periods']==p-1
            assert all(r['available_from_decision_period']<=p for r in context['delivered_reports'])
            assert len(context['last_two_events'])==s['event']-1 if s['event']<=3 else len(context['last_two_events'])==2
            if m=='no_feedback':assert s['search_revision_feedback'] is None
            else:assert len(s['search_revision_feedback'])==4
            if m=='deterministic_search':
                a=s['candidate_construction'];assert a['initial_score_calls']<=27 and a['refinement_score_calls']==6
    if not offline:
        for c in calls:
            assert c['request']['model']=='deepseek-flash'
            content=c['request']['messages'][1]['content']
            context=__import__('json').loads(content)
            assert context['available_report']['observed_periods']==c['decision_period']-1
            assert 'validation_candidate' not in context and 'validation_zero' not in context
    result=dict(status='passed',episodes=len(episodes),unique_node_periods=len(rows),raw_cost_recomputed=True,
        models_frozen=True,causal_reports=True,method_budget_checked=True,offline_fixture=offline,
        actual_changed_decisions=changed,shock_decisions=decision_count,
        raw_sha256={p.name:digest(p) for p in directory.glob('*') if p.is_file() and p.name!='audit.json'})
    write(directory/'audit.json',result)
    return result
