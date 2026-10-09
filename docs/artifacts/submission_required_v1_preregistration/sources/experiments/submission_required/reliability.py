"""Resources from all existing common-comparison attempts, without new API."""
from collections import Counter
import math
from common import ROOT,OUTPUT,read,write,digest,calls_under,usage

def quantile(values,q):
    if not values:return None
    a=sorted(values);x=(len(a)-1)*q;lo=math.floor(x);hi=math.ceil(x)
    return a[lo]+(a[hi]-a[lo])*(x-lo)

def summarize_resources(root):
    calls=calls_under(root)
    events=[];failures=[];completed=[];files={}
    for p in root.rglob('scores.json'):
        events.extend(dict(source=str(p),**s) for s in read(p));files[str(p)]=digest(p)
    for p in root.rglob('runtime_failures.json'):failures.extend(read(p));files[str(p)]=digest(p)
    for p in root.rglob('calls.json'):files[str(p)]=digest(p)
    for p in root.rglob('completed.json'):
        completed.append(read(p));files[str(p)]=digest(p)
    seconds=[c['seconds'] for c in calls if isinstance(c.get('seconds'),(int,float))]
    generated=[s for s in events if s.get('generation_event')]
    return dict(http_requests=len(calls),semantic_requests=sum(c.get('attempt')==1 for c in calls),token_usage=usage(calls),
        status_counts=dict(Counter(c.get('status') for c in calls)),failure_counts=dict(Counter(c.get('failure_kind') for c in calls if c.get('status')!='valid')),
        format_repairs=sum(c.get('attempt',1)>1 for c in calls),http_seconds_total=sum(seconds),http_latency_median=quantile(seconds,.5),http_latency_p95=quantile(seconds,.95),
        generation_events=len(generated),initial_generation_fallbacks=sum(s.get('failure')=='generation_failed' for s in generated),
        revision_failures=sum(bool(s.get('revision_failed')) for s in generated),execution_fallbacks=len(failures),
        screening_records=len(events),selector_seconds_total=sum(s.get('seconds',0) for s in events),
        feedback_score_seconds_total=sum(s.get('revision_scoring_seconds',0) for s in generated),
        candidate_build_seconds_total=sum(s.get('candidate_construction',{}).get('initial_seconds',0)+s.get('candidate_construction',{}).get('refinement_seconds',0) for s in generated),
        all_attempts_included=True,actual_bill_available=False,source_sha256=files)

def historical():
    root=ROOT/'results/joint_baseline_confirmation/confirmation_v1'
    result=summarize_resources(root/'runs')
    assert result['http_requests']==read(root/'completed.json')['api_requests']==1713
    assert result['token_usage']==read(root/'summary.json')['token_usage']
    result.update(scope='Historical common comparison including failed quota attempts; no new API or simulation',
        root_summary_sha256=digest(root/'summary.json'),root_manifest_sha256=digest(root/'manifest.json'))
    write(OUTPUT/'historical_resources.json',result)
    report=ROOT/'docs/2026-10-09-online-resources-results.md'
    report.write_text('# 实时策略运行开销：既有共同测试复核\n\n'
        f"全部历史成功和失败尝试共{result['http_requests']} HTTP、{result['semantic_requests']}语义请求、{result['token_usage'].get('total_tokens')} tokens。"
        f"HTTP耗时中位数{result['http_latency_median']:.3f}秒，P95 {result['http_latency_p95']:.3f}秒。格式失败{result['failure_counts'].get('format',0)}次，执行回退{result['execution_fallbacks']}次。\n\n"
        '请求次数与原1713请求摘要、全部tokens逐项一致。本次无API、无训练、无仿真；HTTP失败与余额恢复费用包含在总数。延迟为同步请求实测，不代表现实救灾时限；未取得实际账单。完整来源SHA、各状态和筛选耗时保存在results/submission_required/v1/historical_resources.json。新实验开销将独立记录，不与历史混算。\n',encoding='utf-8')
    return result

if __name__=='__main__':
    r=historical();print('HISTORICAL_RESOURCES_AUDITED',r['http_requests'],r['semantic_requests'])
