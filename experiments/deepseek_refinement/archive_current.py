"""Recompute completed v2 episode metrics and retain compressed research artifacts."""
import csv
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import numpy as np
from current import ROOT, read, write, training


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',type=int,choices=(2,3),default=2)
    version=parser.parse_args().version
    run_name='llm_current_v2' if version==2 else 'llm_evolution_v3'
    source=ROOT/'results'/run_name;export=ROOT/'docs/artifacts'/run_name
    if export.exists(): raise RuntimeError('Refuse overwrite')
    assert read(source/'completed.json')['status']=='completed'
    records=[];rows_total=0;episodes_total=0;wall=0
    for directory in sorted(source.iterdir()):
        if not directory.is_dir() or not (directory/'episodes.json').exists(): continue
        done=read(directory/'completed.json');seed=int(re.search(r'_seed(\d+)_',directory.name).group(1))
        expected=read(training(seed)/'completion_audit.json')['model_matches']['official_best']['sha256']
        assert done['calls']==done['training_updates']==0 and not done['runtime_failures']
        assert all(c['unchanged'] and c['before']==expected for c in done['parameter_checks'].values())
        with (directory/'periods.csv').open(encoding='utf-8') as stream: rows=list(csv.DictReader(stream))
        assert len(rows)==done['rows'];grouped={}
        for row in rows:
            assert float(row['cost'])==int(row['inventory'])+int(row['backlog'])
            grouped.setdefault((row['group'],row['scenario'],int(row['trace'])),[]).append(row)
        episodes=read(directory/'episodes.json');assert len(episodes)==done['episodes']
        for episode in episodes:
            subset=grouped[episode['group'],episode['scenario'],episode['trace']]
            assert len(subset)==600
            assert math.isclose(sum(float(r['cost']) for r in subset)/600,episode['cost'],abs_tol=1e-9)
            assert math.isclose(sum(int(r['backlog']) for r in subset if int(r['node'])==0)/200,episode['downstream_backlog'],abs_tol=1e-9)
            records.append({'evaluation':directory.name,'seed':seed,**episode})
        demands=read(directory/'demands.json')
        for item in read(directory/'information_audits.json'):
            completed=item['decision_period']-1;through=completed//3*3
            actual=demands[item['scenario']][item['trace']]
            history=[sum(actual[i:i+3])/3 for i in range(0,through,3) for _ in range(3)]
            assert item['reconstructed_history']==history and item['delivered_through_period']==through
        methods={r['group'] for r in rows}
        for trace in range(4):
            reference=grouped['happo','base',trace]
            keys=('period','node','cost','inventory','backlog','actual_order')
            for group in methods:
                assert [tuple(r[k] for k in keys) for r in grouped[group,'base',trace]]==[tuple(r[k] for k in keys) for r in reference]
        rows_total+=len(rows);episodes_total+=len(episodes);wall+=done['wall_seconds']
    assert episodes_total==(1600 if version==2 else 2360) and rows_total==episodes_total*600
    prefix='confirmation' if version==2 else 'test'
    new=read(source/f'{prefix}_new_summary.json');old=read(source/f'{prefix}_old_summary.json')
    for label,summary in ((f'{prefix}_new',new),(f'{prefix}_old',old)):
        for item in summary['fitness']:
            batch=item['trajectory']//4+1;trace=item['trajectory']%4
            episode=next(r for r in records if r['evaluation']==f"{label}_seed{item['seed']}_batch{batch}"
                         and r['trace']==trace and r['group']==item['group'] and r['scenario']=='shock')
            assert item['cost']==episode['cost'] and item['backlog']==episode['downstream_backlog']
    def matrix(summary,group):
        return np.array([[next([r['cost'],r['backlog']] for r in summary['fitness'] if r['seed']==seed and r['trajectory']==trace and r['group']==group) for trace in range(20)] for seed in range(11,16)])
    import sys
    sys.path.insert(0,str(ROOT/'experiments/formal_evaluation'))
    from analyze_multi import compare
    summary=read(source/('confirmation_summary.json' if version==2 else 'test_summary.json'))
    for key,ref,method in (('vs_happo',matrix(new,'happo'),matrix(new,'llm_library')),
                           ('vs_old',matrix(old,'llm_library'),matrix(new,'llm_library')),
                           ('vs_random',matrix(new,'random_screen'),matrix(new,'llm_library'))):
        actual=compare(ref,method)
        assert actual==summary[('new_'+key) if version==2 else key]
    calls=read(source/'calls.json')
    usage={key:sum(c.get('usage',{}).get(key,0) for c in calls) for key in ('prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens')}
    export.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file(): shutil.copy2(path,export/path.name)
        elif path.name=='sources' or path.name in ('confirmation_inputs','test_inputs'): shutil.copytree(path,export/path.name)
        elif (path/'episodes.json').exists():
            target=export/path.name;target.mkdir()
            for file in path.iterdir():
                if not file.is_file(): continue
                if file.name in ('periods.csv','scores.json','information_audits.json','delivered_reports.json'):
                    with file.open('rb') as src,gzip.open(target/(file.name+'.gz'),'wb') as dst: shutil.copyfileobj(src,dst)
                else: shutil.copy2(file,target/file.name)
    if version==3:
        for name,expected in read(source/'manifest.json')['source_sha256'].items():
            path=ROOT/name
            assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
            target=export/'sources'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    write(export/'verification.json',{'episodes':episodes_total,'node_periods':rows_total,'raw_cost_backlog_normal_actions_and_report_timing':'passed',
                                     'all_confirmation_statistics_recomputed':True,'summed_evaluation_wall_seconds':wall,
                                     'api_requests':len(calls),'api_failed':sum(c['status']=='failed' for c in calls),'api_usage':usage,
                                     'currency_cost':None,'cost_note':'Usage recorded; billing currency cost not independently obtained'})
    write(export/'export_hashes.json',{str(p.relative_to(export)):hashlib.sha256(p.read_bytes()).hexdigest() for p in export.rglob('*') if p.is_file()})
    print('ARCHIVED',episodes_total,'episodes',rows_total,'node-periods',usage,flush=True)


if __name__=='__main__': main()
