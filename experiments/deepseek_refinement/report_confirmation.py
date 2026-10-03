"""Publish the complete confirmation record without selecting favourable batches."""
import argparse
import json
from pathlib import Path
import shutil
import os

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);p=parser.parse_args().directory.resolve()
    state=json.loads((p/'progress.json').read_text())
    assert state['status']=='completed' and len(state['batches'])==5
    s=json.loads((p/'summary.json').read_text());assert s['n_demands']==20
    key=os.environ.get('DEEPSEEK_API_KEY')
    export=ROOT/'docs/artifacts'/p.name;export.mkdir(parents=True,exist_ok=True)
    failed=invalid=0;feedback=screening=0.;audits=[]
    for batch in state['batches']:
        source=p.parent/batch['name'];dest=export/batch['name'];dest.mkdir(exist_ok=True)
        for file in source.iterdir():
            if file.is_file():
                if key and file.suffix in ('.json','.csv','.txt','.log'):
                    assert key not in file.read_text(encoding='utf-8')
                shutil.copy2(file,dest/file.name)
        log=p/(batch['name']+'.log')
        if key:assert key not in log.read_text(encoding='utf-8')
        shutil.copy2(log,dest/'train.txt')
        calls=json.loads((source/'calls.json').read_text())
        failed+=sum(c['status']!='valid' for c in calls)
        invalid+=sum(len(c.get('invalid_candidates',[])) for c in calls)
        completed=json.loads((source/'completed.json').read_text())
        assert completed['rows']==19200 and completed['training_updates']==0 and not completed['runtime_failures']
        assert all(h['unchanged'] for h in completed['parameter_checks'].values())
        audits+=completed['branch_audits']
        feedback+=sum(c['seconds'] for c in completed['feedback_times'])
        screening+=sum(c['seconds'] for c in json.loads((source/'scores.json').read_text()))
    assert len(audits)==20 and all(a['shadow_cost']==a['observed_cost'] and a['shadow_backlog']==a['observed_backlog'] for a in audits)
    for file in p.iterdir():
        if file.is_file() and file.suffix in ('.json','.csv','.png','.pdf'):
            shutil.copy2(file,export/file.name)
    labels={'happo':'原HAPPO','manual_screen':'人工规则+筛选','llm_single':'单次LLM+筛选','llm_iterative':'迭代LLM+筛选'}
    ref=s['absolute_means']['happo'];lines=['# 固定v3：20条全新需求确认结果','',
        '按2026-10-03-llm-confirmation-20.md预定方案完整运行5批。未按中途成绩筛选批次、需求或修改算法；源码哈希与开始时一致。','',
        '## 全部冲击回合的均值','',
        '| 方法 | 系统成本/节点期 | 下游平均积压 | 成本较原模型下降 | 积压较原模型下降 |',
        '|---|---:|---:|---:|---:|']
    for g,v in s['absolute_means'].items():
        lines.append(f'|{labels[g]}|{v[0]:.4f}|{v[1]:.4f}|{100*(ref[0]-v[0])/ref[0]:.2f}%|{100*(ref[1]-v[1])/ref[1]:.2f}%|')
    lines+=['','正常情形各组完全一致，因为可靠通知假设下正常回合没有通知。不能据此证明假通知、漏通知或仅需求自动检测的效果。','',
        '## 逐条配对差与不确定性','',
        '差值为方法减原HAPPO，负值表示该指标改善。20个需求回合为重采样单位，固定20000次bootstrap及95%百分位区间，未把节点期当成独立样本。','',
        '| 方法 | 平均成本差及95%区间 | 平均积压差及95%区间 | 成本改善/退化条数 | 积压改善/退化条数 | 两项均严格改善条数 |',
        '|---|---|---|---:|---:|---:|']
    for g,a in s['analysis'].items():
        m=a['mean_delta'];lo,hi=a['ci95']
        lines.append(f"|{labels[g]}|{m[0]:.4f} [{lo[0]:.4f}, {hi[0]:.4f}]|{m[1]:.4f} [{lo[1]:.4f}, {hi[1]:.4f}]|{a['lower_cost_cases']}/{a['higher_cost_cases']}|{a['lower_backlog_cases']}/{a['higher_backlog_cases']}|{a['both_lower_cases']}/20|")
    a=s['analysis']['llm_iterative']
    if a['both_ci_upper_below_zero']:
        conclusion='迭代方案两项配对均值的区间上限均低于0，支持当前仿真分布、单个冻结HAPPO训练种子下的平均改善。不能据此声称所有个案改善、所有现实场景有效或LLM在所有对照中最佳。'
    elif all(x<0 for x in a['mean_delta']):
        conclusion='迭代方案在本批样本两项均值改善，但至少一个区间包含0；未达到预定较强改善证据标准，不能将平均下降当作已验证稳定优势。'
    else:
        conclusion='迭代方案至少一项平均差未改善，本轮未达到相对原模型的两指标改善目标。保留全部结果后继续诊断。'
    v=s['absolute_means']['llm_iterative'];manual=s['absolute_means']['manual_screen']
    lines+=['','## 可支持的结论','',conclusion,'',
        f'人工对照的成本比迭代方案{"低" if manual[0]<v[0] else "高或相同"}，下游积压比迭代方案{"低" if manual[1]<v[1] else "高或相同"}。必须同时呈现，不能忽略更优人工结果。此均值比较不是额外的显著性检验。',
        '', '## 调用、计算和实现检查','',
        f"- 本确认实验{s['usage']['calls']}次API请求，失败或无有效候选请求{failed}次、语法无效候选{invalid}条，均保留且未自动重试。记录总tokens={s['usage']['tokens']}，未推算货币账单。",
        f"- API等待{s['usage']['api_seconds']:.2f}秒；预测筛选{screening:.2f}秒；反馈评分{feedback:.2f}秒；5批总墙钟{s['usage']['wall_seconds']:.2f}秒（包括加载、写文件、运行四组等）。",
        '- 160回合、96000节点期；无训练更新，全部模型哈希不变。每期白名单克隆状态核对通过；20条原HAPPO的20期零修正影子回放成本/下游积压与已发生轨迹完全一致。',
        '- API和评分期间仿真暂停；不是需求继续到达时的部署时延测试。预测是过去需求经验样本，筛选结果不保证真实改善。',
        '- 仅一个训练种子、固定需求冲击分布、可靠现场通知。需多训练种子/多次生成、等候选数与去反馈消融、通知可靠性及真实需求校准后支持更广结论。',
        '', '## 可复查产物','',
        '- [完整汇总](artifacts/confirmation_v3_20/summary.json)',
        '- [全部20条逐项配对差](artifacts/confirmation_v3_20/paired.csv)',
        '- [学习后固定模型的对照图](artifacts/confirmation_v3_20/confirmation.png)',
        '- 各批子目录含全部需求、API响应与规则、搜索/留出预测分数、逐期记录、原模型哈希及回放核对，不发布密钥、上游源码或模型权重。','']
    target=ROOT/'docs/2026-10-03-llm-confirmation-results.md'
    target.write_text('\n'.join(lines),encoding='utf-8')
    print(conclusion)
    print('REPORT',target)


if __name__=='__main__':main()
