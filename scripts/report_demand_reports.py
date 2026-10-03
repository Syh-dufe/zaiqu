"""Audit and report all three fixed periodic-report development settings."""
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/artifacts/periodic_reports_development_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    if OUT.exists():
        raise SystemExit('Refuse to overwrite report artifacts')
    batches = []
    paired = []
    baseline = None
    common_demands = None
    groups = ('happo', 'manual_screen', 'llm_library')
    for interval in (1, 3, 5):
        name = f'reports_k{interval}_development_v1'
        directory = ROOT / 'results/deepseek_refinement' / name
        done = read(directory / 'completed.json')
        protocol = read(directory / 'protocol.json')
        demands = read(directory / 'demands.json')
        episodes = read(directory / 'episodes.json')
        summaries = read(directory / 'summary.json')
        info = read(directory / 'information_audits.json')
        reports = read(directory / 'delivered_reports.json')
        assert done['episodes'] == 24 and done['rows'] == 14400
        assert done['report_interval'] == interval and len(info) == 4800
        assert done['training_updates'] == 0 and done['calls'] == 0
        assert not read(directory / 'calls.json') and not done['runtime_failures']
        assert all(v['unchanged'] for v in done['parameter_checks'].values())
        assert len(done['branch_audits']) == 4
        assert protocol['manual_strengths'] == [.5, 1., 1.5]
        for source, expected in protocol['source_sha256'].items():
            assert hashlib.sha256((ROOT / 'experiments/deepseek_refinement' / source).read_bytes()).hexdigest() == expected
        library = ROOT / 'docs/artifacts/operator_discovery_v1/repaired_library.json'
        assert hashlib.sha256(library.read_bytes()).hexdigest() == protocol['operator_library_sha256']
        if common_demands is None:
            common_demands = demands
        assert common_demands == demands
        current_baseline = [(e['scenario'], e['trace'], e['cost'], e['downstream_backlog'])
                            for e in episodes if e['group'] == 'happo']
        if baseline is None:
            baseline = current_baseline
        assert baseline == current_baseline
        for record in reports:
            end = record['end_period']
            assert end % interval == 0
            assert record['start_period'] == end - interval + 1
            assert record['delivered_after_period'] == end
            assert record['available_from_decision_period'] == end + 1
            trace = demands[record['scenario']][record['trace']]
            assert record['demand_total'] == sum(trace[end-interval:end])
        for record in info:
            period = record['decision_period'] - 1
            end = period // interval * interval
            assert record['observed_periods'] == period
            assert record['delivered_through_period'] == end
            assert record['report_age'] == period - end
            trace = demands[record['scenario']][record['trace']]
            expected = []
            for i in range(0, end, interval):
                expected.extend([sum(trace[i:i+interval])/interval] * interval)
            assert record['reconstructed_history'] == expected
            recent = statistics.mean(expected[-5:]) if expected else 10.
            historical = statistics.mean(expected[-25:-5]) if len(expected) >= 25 else recent
            for features in record['rule_features']:
                assert math.isclose(features['recent'], recent, abs_tol=1e-12)
                assert math.isclose(features['baseline'], historical, abs_tol=1e-12)
            latest = record['latest_report']
            assert latest is None if end == 0 else latest['available_from_decision_period'] <= record['decision_period']
        for trace in range(4):
            normal = [e for e in episodes if e['scenario'] == 'base' and e['trace'] == trace]
            assert len({(e['cost'], e['downstream_backlog']) for e in normal}) == 1
            reference = next(e for e in episodes if e['scenario'] == 'shock' and e['group'] == 'happo' and e['trace'] == trace)
            for group in groups:
                value = next(e for e in episodes if e['scenario'] == 'shock' and e['group'] == group and e['trace'] == trace)
                paired.append(dict(interval=interval, trace=trace, group=group, cost=value['cost'],
                                   backlog=value['downstream_backlog'], cost_delta=value['cost']-reference['cost'],
                                   backlog_delta=value['downstream_backlog']-reference['downstream_backlog']))
        means = summaries['summary']
        batches.append(dict(interval=interval, name=name, means={g:means[g]['shock'] for g in groups},
                            screening=summaries['screening'], wall_seconds=done['wall_seconds'],
                            audited_decisions=len(info), audited_deliveries=len(reports),
                            model_hash=done['parameter_checks']['happo']['before']))
    OUT.mkdir(parents=True)
    for batch in batches:
        directory = ROOT / 'results/deepseek_refinement' / batch['name']
        target = OUT / batch['name']
        target.mkdir()
        for path in directory.iterdir():
            if path.suffix not in ('.json', '.csv', '.png', '.pdf'):
                continue
            if path.stat().st_size > 1_000_000 or path.suffix == '.csv':
                (target / (path.name+'.gz')).write_bytes(gzip.compress(path.read_bytes(), mtime=0))
            else:
                shutil.copy2(path, target / path.name)
        shutil.copy2(ROOT / 'results/learning_curve' / (batch['name']+'_eval.log'), target / 'evaluation.txt')
    result = dict(batches=batches, paired=paired, distinct_demand_traces=4, episodes=72,
                  api_calls=0, training_updates=0,
                  interpretation='Development sensitivity experiment; repeated settings share 4 demand traces, not 12 independent samples.')
    (OUT / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    with (OUT / 'paired.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(paired[0]))
        writer.writeheader(); writer.writerows(paired)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    colors = dict(happo='#555555', manual_screen='#cf8b27', llm_library='#277bb8')
    labels = dict(happo='Frozen HAPPO', manual_screen='Manual + screen', llm_library='LLM library + screen')
    for ax, metric, title in zip(axes, ('cost', 'downstream_backlog'), ('Cost / node-period', 'Downstream mean backlog')):
        for group in groups:
            values = [b['means'][group][metric] for b in batches]
            ax.plot((1, 3, 5), values, marker='o', color=colors[group], label=labels[group])
        ax.set_xticks((1, 3, 5)); ax.set_xlabel('Demand report interval (periods)'); ax.set_ylabel(title)
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('Periodic demand reports: 4 paired development traces')
    fig.tight_layout(); fig.savefig(OUT / 'comparison.png', dpi=180); fig.savefig(OUT / 'comparison.pdf'); plt.close(fig)
    lines = ['# 定期需求报告：小型开发实验结果', '',
             '相同4条新需求轨迹，报告间隔1、3、5周期；3方法及正常/突发情形，共72回合。'
             '冻结HAPPO，API请求0，训练更新0。三档共享4条轨迹，不能当作12条独立样本。', '',
             '| 上报间隔 | 方法 | 平均系统成本/节点周期 | 下游平均积压 |',
             '|---:|---|---:|---:|']
    for batch in batches:
        for group in groups:
            v = batch['means'][group]
            lines.append(f"| {batch['interval']} | {labels[group]} | {v['cost']:.4f} | {v['downstream_backlog']:.4f} |")
    lines += ['', '## LLM相对原HAPPO', '']
    for batch in batches:
        interval = batch['interval']; ref = batch['means']['happo']; new = batch['means']['llm_library']
        cases = [p for p in paired if p['interval'] == interval and p['group'] == 'llm_library']
        cost_change = (new['cost']/ref['cost']-1)*100
        backlog_change = (new['downstream_backlog']/ref['downstream_backlog']-1)*100 if ref['downstream_backlog'] else None
        lines.append(f"- {interval}周期：成本变化{cost_change:+.2f}%，积压变化{backlog_change:+.2f}%；"
                     f"成本改善/退化/持平{sum(p['cost_delta']<0 for p in cases)}/{sum(p['cost_delta']>0 for p in cases)}/{sum(p['cost_delta']==0 for p in cases)}，"
                     f"积压改善/退化/持平{sum(p['backlog_delta']<0 for p in cases)}/{sum(p['backlog_delta']>0 for p in cases)}/{sum(p['backlog_delta']==0 for p in cases)}。")
    lines += ['', '## 核查与限制', '',
              '- 三档真实需求和事件完全一致，原HAPPO逐回合结果一致；正常情形三方法一致。',
              '- 共14400次决策的信息记录核对完成；重建历史只覆盖已送达报告区间，报告总量与真实历史汇总一致。',
              '- 三档源代码/库哈希一致，各方法模型哈希不变；原策略影子回放审计完成，无记录的运行失败。',
              '- 人工对照固定3档修正强度，与3条LLM规则同候选数；该人工对照与旧实验的单候选不同。',
              '- 信息间隔同时带来滞后与区间平滑，不能把差异全部解释成延迟效应。',
              '- 即时库存、积压、本地订单和HAPPO建议仍可见；这不是全系统信息延迟。可靠灾情通知仍保留。',
              '- 预测报告均值视作近似潜在需求、待上报过去片段以最后均值填充；不声称精确贝叶斯后验。',
              '- 仅4条开发轨迹和1个冻结模型，不作显著性或普遍最优结论，也不用于真实洪灾部署结论。',
              '- 仿真在预测计算时暂停，运行耗时不是实时部署吞吐性能。', '',
              '全部逐轨迹差异和原始信息记录（大文件gzip压缩）见 '
              '[产物目录](artifacts/periodic_reports_development_v1/summary.json)。', '',
              '![对比图](artifacts/periodic_reports_development_v1/comparison.png)', '']
    (ROOT / 'docs/2026-10-03-periodic-demand-reports-results.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(dict(batches=batches, episodes=72, audited_decisions=14400), indent=2))


if __name__ == '__main__':
    main()
