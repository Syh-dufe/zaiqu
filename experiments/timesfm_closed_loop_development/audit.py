"""Raw audit adapted explicitly to forecast groups; no swallowing failures."""
import inspect
import csv
import json
import hashlib
from pathlib import Path

def audit(runner,directory,data,expected_hash,offline=False):
    core=runner.core;ROOT=runner.ROOT;methods=runner.METHODS
    legacy=runner.module('timesfm_explicit_raw_auditor',ROOT/'experiments/submission_required/audit.py')
    text=inspect.getsource(legacy.audit)
    needle="('online_feedback','no_feedback','no_review','first_only')"
    assert text.count(needle)==1;text=text.replace(needle,repr(methods))
    needle="context=__import__('json').loads(content)"
    assert text.count(needle)==1
    text=text.replace(needle,needle+";context=context.get('context',context)")
    ns=dict(legacy.__dict__);exec(compile(text,str(Path(__file__)),'exec'),ns)
    result=ns['audit'](directory,methods,data,expected_hash,offline)
    directory=Path(directory);scores=core.read(directory/'scores.json');policy=runner.guard.policy
    infos={(i['group'],i['scenario'],i['trace'],i['decision_period']):i for i in core.read(directory/'information_audits.json')}
    event_map={(r['group'],r['scenario'],r['trace'],r['decision_period']):r for r in scores}
    rules_module=runner.module('timesfm_execution_rules',ROOT/'experiments/deepseek_pilot/rules.py')
    with (directory/'periods.csv').open(encoding='utf-8',newline='') as f:
        raw_rows=list(csv.DictReader(f))
    row_map={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in raw_rows}
    for group in methods:
        for scenario in ('base','shock'):
            for trace in range(4):
                candidates={}
                for period in range(1,201):
                    identity=(group,scenario,trace,period);record=event_map.get(identity)
                    if record and record.get('generation_event'):
                        candidates={c['id']:rules_module.compile_rule(c['rule']) for c in record['candidates'] if c['id']!='zero'}
                    info=infos[identity]
                    for node in range(3):
                        row=row_map[identity+(node,)];chosen=row['chosen']
                        assert info['chosen']==chosen
                        expected=int(row['policy_order'])
                        if chosen!='zero':
                            delta=rules_module.rule_delta(candidates[chosen],info['rule_features'][node])
                            expected=rules_module.bounded_order(expected,delta)
                        assert expected==int(row['actual_order']),'Executed DSL correction mismatch'
    for r in scores:
        if r.get('execution_failure'):continue
        if r.get('generation_event') and r.get('revision_guard_audit'):
            a=r['revision_guard_audit'];assert a['adopted']==policy.keep_revision(a['original_score'],a['revised_score'],r['search_revision_feedback'][0])
        ranked=sorted((i for i in range(1,4) if policy.eligible(r['search'][i],r['search'][0])),key=lambda i:(r['search'][i]['cost'],i))
        expected='zero';actual=r['review_candidates'];assert len(actual)<=len(ranked)
        for i,item in zip(ranked,actual):
            assert item['id']==r['search'][i]['id'] and item['passed']==policy.eligible(item['score'],r['validation_zero'])
            if item['passed']:assert item is actual[-1];expected=item['id']
        if expected=='zero':assert len(actual)==len(ranked)
        assert r['chosen']==expected and r['candidate_score_calls']<=8
        a=r['forecast_audit'];p=r['decision_period'];trace=r['trace']
        assert a['group']==r['group'] and a['decision_period']==p and a['report_age']==(p-1)%3
        history=[sum(data['shock'][trace][i:i+3])/3 for i in range(0,p-1-(p-1)%3,3)]
        reconstructed=[v for x in history for v in [x]*3]
        if r['group']=='original_merton':
            pair=runner.original.forecasts(reconstructed,trace,p-1,'merton',a['report_age'])
        else:
            if r['group']=='center_naive':assert a['center']==[history[-1]]*a['horizon']
            elif r['group']=='center_merton':
                import numpy as np
                old=runner.original.forecasts(reconstructed,trace,p-1,'merton',a['report_age'])
                assert a['center']==np.asarray(old[0]+old[1]).mean(axis=0).tolist()
            else:
                assert a['prediction']['block_history']==history
                import numpy as np
                point=a['prediction']['block_predictions']
                assert a['center']==np.clip(np.repeat(point,3)[a['report_age']:a['report_age']+a['horizon']],0,20).tolist()
                assert a['prediction']['revision']==runner.predictor.REVISION
            v=runner.paths.generate(a['center'],history[-1],a['report_age'],a['stream_identity'])
            assert v['stream_seeds']==a['stream_seeds'];pair=v['deployment'][:3],v['deployment'][3:]
        assert json.dumps(pair)==json.dumps(r['forecasts'])
    # All normal and pre-notice actor/environment records match cached frozen HAPPO.
    seed=core.read(directory/'protocol.json')['training_seed']
    batch=next(r['forecast_audit']['batch'] for r in scores if 'forecast_audit' in r)
    cached=ROOT/f'results/online_llm_guard_pool/development_v1/runs/development_batch{batch:02d}_seed{seed}'
    with (cached/'periods.csv').open(encoding='utf-8',newline='') as f:
        reference={(r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in csv.DictReader(f) if r['group']=='guard_pool'}
    with (directory/'periods.csv').open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            s,t,p,n=r['scenario'],int(r['trace']),int(r['period']),int(r['node'])
            if s=='base' or p<data['events'][t]['start_index']+3:
                assert all(r[k]==reference[s,t,p,n][k] for k in ('cost','inventory','backlog','policy_order','actual_order'))
    result.update(guard_pool_decisions_recomputed=True,forecast_paths_recomputed=True,executed_dsl_actions_recomputed=True,cached_normal_pre_notice_exact=True,
        source_sha256=core.source_hashes(),system_sha256=hashlib.sha256(core.SYSTEM.encode()).hexdigest())
    core.write(directory/'audit.json',result);return result
