"""Summarize every case, including failures and prediction screening overhead."""
import argparse
import csv
import json
from pathlib import Path
import statistics


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);root=p.parse_args().directory
    read=lambda n:json.loads((root/n).read_text(encoding='utf-8'))
    episodes=read('episodes.json');calls=read('calls.json');scores=read('scores.json');done=read('completed.json');demands=read('demands.json')
    rows=list(csv.DictReader((root/'periods.csv').open(encoding='utf-8')))
    assert all(c['unchanged'] for c in done['parameter_checks'].values())
    assert all(0<=int(r['actual_order'])<=20 and abs(int(r['actual_order'])-int(r['happo_order']))<=6 for r in rows)
    paired=[];summary={};prediction_errors=[]
    groups=sorted({e['group'] for e in episodes})
    for group in groups:
        summary[group]={}
        for scenario in ('base','shock'):
            es=[e for e in episodes if e['group']==group and e['scenario']==scenario]
            summary[group][scenario]={k:statistics.mean(e[k] for e in es) for k in ('cost','downstream_backlog')}
            for e in es:
                ref=next(x for x in episodes if x['group']=='happo' and x['scenario']==scenario and x['trace']==e['trace'])
                paired.append(dict(group=group,scenario=scenario,trace=e['trace'],
                                   cost_delta=e['cost']-ref['cost'],backlog_delta=e['downstream_backlog']-ref['downstream_backlog']))
    for s in scores:
        true=demands['shock'][s['trace']][s['period']-1:s['period']-1+len(s['forecasts'][0][0])]
        path=s['forecasts'][0]+s['forecasts'][1]
        prediction_errors.append(dict(group=s['group'],trace=s['trace'],period=s['period'],
             mean_absolute_error=statistics.mean(abs(statistics.mean(p[t] for p in path)-d) for t,d in enumerate(true))))
    screening={g:dict(evaluations=sum(s['group']==g for s in scores),
                     accepted=sum(s['group']==g and s['chosen']!='zero' for s in scores),
                     seconds=sum(s['seconds'] for s in scores if s['group']==g)) for g in groups}
    result=dict(summary=summary,screening=screening,api_calls=sum(not c.get('replayed',False) for c in calls),
                replayed_calls=sum(c.get('replayed',False) for c in calls),
                failed_calls=sum(c['status']!='valid' and not c.get('replayed',False) for c in calls),
                tokens=sum(c.get('response',{}).get('usage',{}).get('total_tokens',0) for c in calls if not c.get('replayed',False)),
                api_seconds=sum(c['seconds'] for c in calls),
                paired=paired,prediction_mean_absolute_error=statistics.mean(e['mean_absolute_error'] for e in prediction_errors),
                interpretation='Small batch; no significance or general superiority claim. API and screening pause simulator. Extra information and computation differ from original actors.')
    (root/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    with (root/'prediction_errors.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(prediction_errors[0]));w.writeheader();w.writerows(prediction_errors)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,key,title in zip(axes,('cost','downstream_backlog'),('System cost / node-period','Downstream mean backlog')):
        ax.bar(groups,[summary[g]['shock'][key] for g in groups]);ax.set_title(title)
        ax.tick_params(axis='x',rotation=25);ax.set_ylim(bottom=0)
    fig.suptitle('DeepSeek causal refinement: demand-shock cases');fig.tight_layout()
    fig.savefig(root/'comparison.png',dpi=180);fig.savefig(root/'comparison.pdf');plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
