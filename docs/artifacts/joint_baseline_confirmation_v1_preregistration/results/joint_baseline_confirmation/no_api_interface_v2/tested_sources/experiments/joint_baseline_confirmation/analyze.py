"""Raw-cost audit and preregistered crossed model/path bootstrap for three methods."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np

METHODS=('happo','ippo','online_feedback')
SEEDS=(11,12,13,14,15)
TYPES=('single_surge','sustained_surge','double_surge','surge_then_drop')
COMPARISONS=(('online_feedback','ippo'),('online_feedback','happo'),('ippo','happo'))
METRICS=('shock_cost','shock_backlog','base_cost','base_backlog','cost_did','backlog_did')


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_raw(rows,episodes,data,information,checks,contract):
    expected={(m,s,t,p,n) for m in METHODS for s in ('base','shock') for t in range(4) for p in range(1,201) for n in range(3)}
    keyed={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in rows}
    assert len(rows)==len(keyed)==14400 and set(keyed)==expected
    expected_episodes={(m,s,t) for m in METHODS for s in ('base','shock') for t in range(4)}
    assert len(episodes)==24 and {(e['group'],e['scenario'],e['trace']) for e in episodes}==expected_episodes
    for k,r in keyed.items():
        m,s,t,p,n=k
        assert int(r['demand'])==data[s][t][p-1]
        assert float(r['cost'])==int(r['inventory'])+int(r['backlog'])
        assert 0<=int(r['policy_order'])<=20 and 0<=int(r['actual_order'])<=20
        if m in ('happo','ippo'):assert int(r['policy_order'])==int(r['actual_order']) and r['chosen']=='zero'
        notice=data['events'][t]['start_index']+3
        value=str(notice) if s=='shock' and p>=notice else ''
        assert str(r['notification_period'] or '')==value
    for e in episodes:
        subset=[keyed[e['group'],e['scenario'],e['trace'],p,n] for p in range(1,201) for n in range(3)]
        assert math.isclose(e['cost'],sum(float(r['cost']) for r in subset)/600,abs_tol=1e-10)
        assert math.isclose(e['downstream_backlog'],sum(int(r['backlog']) for r in subset if int(r['node'])==0)/200,abs_tol=1e-10)
        if e['group'] in ('happo','ippo') or e['scenario']=='base':
            assert e['episode_http']==e['generation_events']==0
        assert e['episode_http']<=16 and e['generation_events']<=4
    info={(r['group'],r['scenario'],r['trace'],r['decision_period']):r for r in information}
    assert len(information)==len(info)==4800
    for m,s,t,p,n in expected:
        if n:continue
        r=info[m,s,t,p]
        assert r['observed_periods']==p-1 and r['delivered_through_period']==(p-1)//3*3
    for t,event in enumerate(data['events']):
        for m in METHODS:
            for p in range(1,event['start_index']+1):
                for n in range(3):
                    left,right=keyed[m,'base',t,p,n],keyed[m,'shock',t,p,n]
                    assert all(str(left[k])==str(right[k]) for k in ('cost','inventory','backlog','actual_order','policy_order'))
        for s in ('base','shock'):
            stop=201 if s=='base' else event['start_index']+3
            for p in range(1,stop):
                for n in range(3):
                    left,right=keyed['happo',s,t,p,n],keyed['online_feedback',s,t,p,n]
                    assert all(str(left[k])==str(right[k]) for k in ('cost','inventory','backlog','actual_order','policy_order'))
    for m in METHODS:
        expected_hash=contract['ippo_contract' if m=='ippo' else 'happo_contract']['expected_parameter_sha256']
        assert checks[m]['before']==checks[m]['after']==expected_hash and checks[m]['unchanged']
    return dict(unique_node_periods=len(keyed),cost_recomputed=True,causal_reports=True,models_frozen=True)


def crossed(values,coverage,replicates=20000,seed=20271551):
    # One paired model-axis draw shared across all types and metrics; each type
    # independently draws its ten path identities. Repeated model/path cells
    # are not treated as independent trajectories.
    rng=np.random.default_rng(seed)
    model_indices=rng.integers(0,5,size=(replicates,5))
    overall=np.zeros((replicates,len(METRICS)))
    by_type={}
    def interval(draws,point):
        tail=(1-coverage)/2
        lo,hi=np.quantile(draws,[tail,1-tail],axis=0)
        return {metric:dict(mean=float(point[i]),low=float(lo[i]),high=float(hi[i]),coverage=coverage,replicates=replicates)
                for i,metric in enumerate(METRICS)}
    for t in TYPES:
        a=values[t];assert a.shape==(10,5,len(METRICS)) and np.isfinite(a).all()
        paths=rng.integers(0,10,size=(replicates,10))
        sampled=a[paths[:,:,None],model_indices[:,None,:],:].mean(axis=(1,2))
        overall+=sampled/4
        by_type[t]=interval(sampled,a.mean(axis=(0,1)))
    return dict(overall=interval(overall,np.mean([values[t].mean(axis=(0,1)) for t in TYPES],axis=0)),by_type=by_type,
                sampling='paired model axis shared across types; ten independent paths within each type',seed=seed)


def describe(items):
    return {metric:dict(mean=float(np.mean([p[metric] for p in items])),n=len(items),
                        better=sum(p[metric]<0 for p in items),tied=sum(p[metric]==0 for p in items),worse=sum(p[metric]>0 for p in items))
            for metric in METRICS}


def summarize(out,manifest,finished,audit_child,all_recorded_calls,usage_totals):
    assert len(finished)==50
    epi={};runs=[];row_count=0
    for item in finished.values():
        seed,batch,label=item['seed'],item['batch'],item['run_label']
        entry=manifest['input_batches'][batch-1]
        data=read(Path(entry['path']));a=audit_child(out/'runs'/label,entry,seed)
        row_count+=len(a['rows'])
        for e in a['episodes']:
            key=(seed,batch,e['group'],e['scenario'],e['trace']);assert key not in epi
            epi[key]=e
        runs.append(dict(seed=seed,batch=batch,label=label,episodes=24,node_periods=len(a['rows']),
                         completed_sha256=digest(out/'runs'/label/'completed.json'),runtime_failures=a['runtime_failures']))
    assert len(epi)==1200 and row_count==720000
    comparisons={}
    for left,right in COMPARISONS:
        pairs=[];values={t:np.empty((10,5,len(METRICS))) for t in TYPES}
        for si,seed in enumerate(SEEDS):
            for entry in manifest['input_batches']:
                batch=entry['batch'];data=read(Path(entry['path']))
                for trace,event in enumerate(data['events']):
                    def delta(s,field):return epi[seed,batch,left,s,trace][field]-epi[seed,batch,right,s,trace][field]
                    sc,sb,bc,bb=delta('shock','cost'),delta('shock','downstream_backlog'),delta('base','cost'),delta('base','downstream_backlog')
                    record=dict(seed=seed,batch=batch,trace=trace,type=event['type'],demand_seed=entry['demand_seed'],
                                shock_cost=sc,shock_backlog=sb,base_cost=bc,base_backlog=bb,cost_did=sc-bc,backlog_did=sb-bb)
                    pairs.append(record)
                    values[event['type']][batch-1,si,:]=[record[k] for k in METRICS]
        coverage=.975 if (left,right)==COMPARISONS[0] else .95
        comparisons[f'{left}-minus-{right}']=dict(left=left,right=right,descriptive=describe(pairs),
            bootstrap=crossed(values,coverage),paired_results=pairs,
            by_type={t:describe([p for p in pairs if p['type']==t]) for t in TYPES},
            by_seed={str(s):describe([p for p in pairs if p['seed']==s]) for s in SEEDS})
    main=comparisons['online_feedback-minus-ippo']['bootstrap']['overall']
    primary=dict(comparison='online_feedback-minus-ippo',cost=main['shock_cost'],backlog=main['shock_backlog'],
                 joint_improvement_supported=all(main[k]['mean']<0 and main[k]['high']<0 for k in ('shock_cost','shock_backlog')))
    means={m:{s:{field:float(np.mean([e[field] for (seed,batch,method,scenario,trace),e in epi.items() if method==m and scenario==s]))
                  for field in ('cost','downstream_backlog')} for s in ('base','shock')} for m in METHODS}
    profiles=[]
    for entry in manifest['input_batches']:
        data=read(Path(entry['path']))
        for t,event in enumerate(data['events']):
            parts=[]
            for part in event['intervals']:
                start,end=part['start'],part['end'];base=data['base'][t][start:end];shock=data['shock'][t][start:end]
                b,s=sum(base),sum(shock)
                parts.append(dict(**part,base_total=b,shock_total=s,actual_change_ratio=(s-b)/b if b else None,
                    absolute_change=sum(abs(a-c) for a,c in zip(base,shock)),clipped_periods=sum(part['factor']*a>20 for a in base)))
            profiles.append(dict(batch=entry['batch'],trace=t,type=event['type'],intervals=parts,
                                 unchanged_consumed_path=data['base'][t][:200]==data['shock'][t][:200]))
    calls=all_recorded_calls(out);semantic=sum(c.get('attempt')==1 for c in calls)
    assert len(calls)<=6400 and semantic<=3200
    kinds={}
    for c in calls:
        if c.get('status')!='valid':
            k=c.get('failure_kind','unknown');kinds[k]=kinds.get(k,0)+1
    summary=dict(status='complete',phase='independent_confirmation',development_only=False,episodes=1200,node_periods=720000,
        primary=primary,comparisons=comparisons,method_means=means,actual_profiles=profiles,runs=runs,
        api_requests=len(calls),semantic_requests=semantic,token_usage=usage_totals(calls),api_failure_kinds=kinds,
        api_seconds=sum(c.get('seconds',0) for c in calls),all_attempts_included_in_resources=True,
        historical_api_costs_excluded=True,all_registered_cases_retained=True,
        limitations='Five training seed pairs and forty type-specific demand paths. LLM extra reports/system states/forecast computation mean a system comparison, not isolated semantic or equal-compute superiority.')
    write(out/'summary.json',summary)
    write(out/'completed.json',dict(status='completed',episodes=1200,node_periods=720000,completed_runs=50,
        api_requests=len(calls),semantic_requests=semantic,summary_sha256=digest(out/'summary.json'),training_updates=0,
        all_registered_cases_retained=True))
    return summary
