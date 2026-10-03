"""Analyze every preregistered pair, preserving adverse trajectories."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]


def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def intervals(values):
    rng=np.random.default_rng(20261220)
    draws=values[rng.integers(0,len(values),size=(20000,len(values)))].mean(axis=1)
    return dict(ci95=np.quantile(draws,[.025,.975],axis=0).tolist(),
                ci97p5=np.quantile(draws,[.0125,.9875],axis=0).tolist())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    out=parser.parse_args().directory.resolve()
    state=json.loads((out/'progress.json').read_text(encoding='utf-8-sig'));manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8-sig'))
    if state['status']!='completed' or manifest['mode']!='formal_stage_a' or len(state['completed'])!=5:
        raise RuntimeError('Require all five completed formal batches')
    if (out/'summary.json').exists():raise RuntimeError('Refuse replacing analyzed results')
    pairs=[];all_rows=[];absolute={'happo':[], 'llm_library':[]};checks=[];decisions=[];errors=[]
    for batch_number,record in enumerate(state['completed'],1):
        batch=out/record['name'];done=json.loads((batch/'completed.json').read_text(encoding='utf-8-sig'))
        assert done['episodes']==16 and done['rows']==9600 and done['calls']==done['training_updates']==0 and not done['runtime_failures']
        assert all(x['unchanged'] for x in done['parameter_checks'].values())
        inputs=json.loads((batch/'demands.json').read_text(encoding='utf-8-sig'));source=json.loads((batch/'input_source.json').read_text(encoding='utf-8-sig'))
        source_file=Path(manifest['inputs'][batch_number-1]['path'])
        assert source['sha256']==manifest['inputs'][batch_number-1]['sha256']==hashlib.sha256(source_file.read_bytes()).hexdigest()
        original=json.loads(source_file.read_text(encoding='utf-8-sig'))
        assert all(inputs[k]==original[k] for k in ('base','shock','events','demand_seed','event_seed'))
        episodes=json.loads((batch/'episodes.json').read_text(encoding='utf-8-sig'))
        rows=list(csv.DictReader((batch/'periods.csv').open(encoding='utf-8')))
        for row in rows:
            for key in ('trace','period','node','demand','inventory','backlog','happo_order','actual_order'):row[key]=int(row[key])
            row['cost']=float(row['cost']);row['batch']=batch_number
            assert row['cost']==row['inventory']+row['backlog']
        all_rows+=rows
        for trace in range(4):
            shock={e['group']:e for e in episodes if e['trace']==trace and e['scenario']=='shock'}
            base={e['group']:e for e in episodes if e['trace']==trace and e['scenario']=='base'}
            assert all(base['happo'][k]==base['llm_library'][k] for k in ('cost','downstream_backlog'))
            pair=dict(batch=batch_number,trace=trace,demand_seed=inputs['demand_seed'],event_seed=inputs['event_seed'],**inputs['events'][trace])
            for group in absolute:
                e=shock[group];subset=[r for r in rows if r['group']==group and r['scenario']=='shock' and r['trace']==trace]
                assert len(subset)==600
                assert math.isclose(sum(r['cost'] for r in subset)/600,e['cost'],abs_tol=1e-9)
                lower=[r for r in subset if r['node']==0];event=inputs['events'][trace]
                active=[r for r in lower if event['start_index']<r['period']<=event['start_index']+event['duration']]
                recovery=[r for r in lower if r['period']>event['start_index']+event['duration']]
                pair.update({group+'_cost':e['cost'],group+'_backlog':e['downstream_backlog'],
                             group+'_peak_backlog':max(r['backlog'] for r in lower),
                             group+'_final_backlog':lower[-1]['backlog'],
                             group+'_shock_backlog':float(np.mean([r['backlog'] for r in active])),
                             group+'_recovery_backlog':float(np.mean([r['backlog'] for r in recovery])),
                             group+'_inventory':float(np.mean([r['inventory'] for r in subset]))})
                absolute[group].append([e['cost'],e['downstream_backlog']])
            pair.update(cost_delta=pair['llm_library_cost']-pair['happo_cost'],
                        backlog_delta=pair['llm_library_backlog']-pair['happo_backlog'])
            pairs.append(pair)
        for score in json.loads((batch/'scores.json').read_text(encoding='utf-8-sig')):
            decisions.append(score)
            forecast_start=score['period']-1;actual=inputs['shock'][score['trace']]
            for paths in score['forecasts']:
                for path in paths:errors.extend(abs(float(v)-actual[forecast_start+i]) for i,v in enumerate(path))
        # Public histories and interval calendars are independently checked after execution.
        information=json.loads((batch/'information_audits.json').read_text(encoding='utf-8-sig'))
        assert len(information)==3200
        for item in information:
            completed=item['decision_period']-1;through=completed//3*3
            actual=inputs[item['scenario']][item['trace']]
            expected=[sum(actual[i:i+3])/3 for i in range(0,through,3) for _ in range(3)]
            assert item['reconstructed_history']==expected and item['delivered_through_period']==through and item['report_age']==completed-through
        checks.append(dict(batch=batch_number,rows=len(rows),information_decisions=len(information),
                           original_branch_replays=len(done['branch_audits']),all_model_hashes_unchanged=True))
    assert len(pairs)==20 and len(all_rows)==48000
    means={group:np.mean(v,axis=0).tolist() for group,v in absolute.items()}
    deltas=np.array([[p['cost_delta'],p['backlog_delta']] for p in pairs]);cis=intervals(deltas)
    stronger=bool(np.all(deltas.mean(axis=0)<0) and np.all(np.asarray(cis['ci97p5'])[1]<0))
    counts={name:dict(improved=int(np.sum(deltas[:,i]<-1e-9)),tied=int(np.sum(np.abs(deltas[:,i])<=1e-9)),
                      worsened=int(np.sum(deltas[:,i]>1e-9))) for i,name in enumerate(('cost','backlog'))}
    summary=dict(n_pairs=20,training_seeds=[11],report_interval=3,methods=list(absolute),means=means,
        mean_delta=deltas.mean(axis=0).tolist(),**cis,counts=counts,
        both_strictly_improved=int(np.sum(np.all(deltas<0,axis=1))),stronger_evidence=stronger,
        percent_reduction=(100*(np.array(means['happo'])-means['llm_library'])/means['happo']).tolist(),
        bootstrap_seed=20261220,bootstrap_samples=20000,resampling_unit='paired demand/event trajectory',
        calls=0,training_updates=0,wall_seconds=state['wall_seconds'],
        screening_seconds=sum(d['seconds'] for d in decisions),screening_decisions=len(decisions),
        nonzero_selections=sum(d['chosen']!='zero' for d in decisions),forecast_mae_posthoc=float(np.mean(errors)),
        upstream_revision='a7e5a3e83e21565a5799483bc534e39635ec65dd',
        source_manifest='manifest.json',development_api_history_note='120 requests in prior refinement/discovery series, including failures; not a zero-cost method')
    write(out/'summary.json',summary);write(out/'verification.json',dict(episodes=80,rows=48000,batches=checks,all_inputs_unchanged=True))
    with (out/'paired.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(pairs[0]));writer.writeheader();writer.writerows(pairs)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for i,ax in enumerate(axes):
        ax.bar(np.arange(1,21),deltas[:,i],color=np.where(deltas[:,i]<0,'#287c8e','#c34c3b'))
        ax.axhline(0,color='black',linewidth=.7);ax.set_xlabel('All 20 paired trajectories')
        ax.set_ylabel(('Cost difference per node-period','Downstream backlog difference')[i])
    fig.suptitle('Fixed LLM library + screen minus Frozen HAPPO (seed 11, k=3)');fig.tight_layout()
    for extension in ('png','pdf'):fig.savefig(out/f'paired_differences.{extension}',dpi=160)
    plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True)
    for group,label in (('happo','Frozen HAPPO'),('llm_library','LLM library + screen')):
        cost=[];backlog=[]
        for period in range(1,201):
            subset=[r for r in all_rows if r['group']==group and r['scenario']=='shock' and r['period']==period]
            cost.append(np.mean([r['cost'] for r in subset]));backlog.append(np.mean([r['backlog'] for r in subset if r['node']==0]))
        axes[0].plot(range(1,201),cost,label=label);axes[1].plot(range(1,201),backlog,label=label)
    axes[0].set_ylabel('Mean cost per node');axes[1].set_ylabel('Mean downstream backlog');axes[1].set_xlabel('Simulation period')
    axes[0].legend();fig.suptitle('All trajectories retained; different event start periods');fig.tight_layout()
    for extension in ('png','pdf'):fig.savefig(out/f'mean_timeseries.{extension}',dpi=160)
    plt.close(fig)
    export=ROOT/'docs/artifacts'/out.name
    if export.exists():raise RuntimeError('Refuse overwrite published artifacts')
    export.mkdir(parents=True)
    for file in out.iterdir():
        if file.is_file():shutil.copy2(file,export/file.name)
    for record in state['completed']:
        batch=out/record['name'];dest=export/batch.name;dest.mkdir()
        for file in batch.iterdir():
            if not file.is_file():continue
            if file.name in ('periods.csv','information_audits.json','scores.json'):
                with file.open('rb') as src,gzip.open(dest/(file.name+'.gz'),'wb') as target:shutil.copyfileobj(src,target)
            else:shutil.copy2(file,dest/file.name)
    input_export=export/'inputs';input_export.mkdir()
    for record in manifest['inputs']:shutil.copy2(record['path'],input_export/Path(record['path']).name)
    shutil.copy2(Path(manifest['inputs'][0]['path']).parent/'manifest.json',input_export/'manifest.json')
    rows=['# 阶段A：20条新需求、80回合正式确认','',
          '按固定协议完成全部5批；单个seed11模型，报告间隔3，固定LLM算子库，评估阶段无API、无训练。','',
          '| 方法 | 平均成本/节点期 | 下游平均积压 |','|---|---:|---:|']
    for group,label in (('happo','Frozen HAPPO'),('llm_library','LLM算子库+筛选')):
        rows.append(f'| {label} | {means[group][0]:.4f} | {means[group][1]:.4f} |')
    rows+=['',f"成本均值下降{summary['percent_reduction'][0]:.2f}%，下游积压均值下降{summary['percent_reduction'][1]:.2f}%；下降为负表示退化。",'',
          '| 配对差：方法减HAPPO | 均值 | 95%区间 | 97.5%区间 | 改善/持平/退化 |',
          '|---|---:|---|---|---|']
    for i,name in enumerate(('cost','backlog')):
        counts_i=counts[name]
        rows.append(f"| {name} | {summary['mean_delta'][i]:.4f} | [{cis['ci95'][0][i]:.4f}, {cis['ci95'][1][i]:.4f}] | [{cis['ci97p5'][0][i]:.4f}, {cis['ci97p5'][1][i]:.4f}] | {counts_i['improved']}/{counts_i['tied']}/{counts_i['worsened']} |")
    conclusion='两项均值及各97.5%区间上限均低于0，达到预定的本分布下平均改善证据标准。' if stronger else '未达到预定的两指标同时改善证据标准；保留全部结果，不能宣布稳定优势。'
    rows+=['',conclusion,'',f"20条中两指标都严格改善{summary['both_strictly_improved']}条。多训练种子和机制消融尚未运行。",'',
           '## 口径与限制','',
           '- 基准需求未受冲击时，两方法所有行为相同，不把40个正常回合加入冲击配对统计。',
           '- 每条配对是统计单位，20000次bootstrap、种子20261220；97.5%区间对应两指标Bonferroni名义家族95%，有限样本覆盖不是严格保证。',
           '- 原HAPPO本地信息与修正模块全节点状态/滞后汇总不完全相同。结果评价完整系统，不能单独归因于LLM。',
           '- 事件期在线选择已有LLM算子，并非实时API推理；可靠通知、均值重建报告、固定提前期、单类可补供物资假设均保留；没有真实洪灾数据校准。',
           '- 预测结果不能保证每条真实轨迹改善。所有退化、截断比例、峰值/末期欠货及恢复期欠货见逐条数据。',
           f"- 筛选{summary['screening_decisions']}次，非零采用{summary['nonzero_selections']}次，累计筛选{summary['screening_seconds']:.2f}秒；总墙钟{summary['wall_seconds']:.2f}秒。计算期间仿真暂停，不是实时时延实测。",
           '- 当前评估API为0，但此前改进/发现系列有120次请求（含失败）。调用、修复来源与开发成本记录继续保留。','',
           '## 产物','',f'- [完整统计](artifacts/{out.name}/summary.json)',f'- [全部20条配对](artifacts/{out.name}/paired.csv)',
           f'- [逐批输入、版本与因果审核](artifacts/{out.name}/verification.json)',
           f'![全部配对差](artifacts/{out.name}/paired_differences.png)',f'![平均时序](artifacts/{out.name}/mean_timeseries.png)','']
    (ROOT/'docs/formal-evaluation-stage-a-results.md').write_text('\n'.join(rows),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2));print('REPORT_WRITTEN',flush=True)


if __name__=='__main__':main()
