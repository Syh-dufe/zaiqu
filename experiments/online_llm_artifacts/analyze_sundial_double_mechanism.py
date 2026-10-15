"""Post-hoc read-only stage costs and stored six-path forecast diagnostics."""
import csv,gzip,hashlib,json,statistics,winreg
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/sundial_double_mechanism/six_rules_v1'
STAGES={'before':(1,65),'first_peak':(66,85),'gap':(86,105),'second_peak':(106,125),'after':(126,200)}
LABELS={'before':'冲击前','first_peak':'第一峰','gap':'两峰间隔','second_peak':'第二峰','after':'第二峰结束后'}
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes(json.dumps(v,ensure_ascii=False,indent=2).encode())
def run():
    assert not OUT.exists();OUT.mkdir(parents=True)
    input_path=ROOT/'results/submission_required/v1/inputs/confirmation01_main.json'
    data=read(input_path);event=data['events'][2]
    assert event['type']=='double_surge' and event['intervals']==[dict(start=65,end=85,factor=1.5),dict(start=105,end=125,factor=1.5)]
    truth=np.asarray(data['shock'][2][:200]);inputs={str(input_path):sha(input_path)}
    stages=[];forecast_points=[];generation=[];execution=[]
    for seed in range(11,16):
        dirs={'merton':ROOT/f'results/online_llm_guard_pool/development_v1/runs/development_batch01_seed{seed}',
              'sundial':ROOT/('results/sundial_six_rules/development_v1' if seed<13 else 'results/sundial_six_rules_extension/v1')/f'runs/seed{seed}_four_types'}
        for method,d in dirs.items():
            for name in ('periods.csv','scores.json','episodes.json','demands.json','completed.json','audit.json'):
                inputs[str(d/name)]=sha(d/name)
            assert read(d/'audit.json')['status']=='passed'
            assert read(d/'demands.json')['shock'][2]==data['shock'][2]
            group='guard_pool' if method=='merton' else 'adapted_sundial'
            with (d/'periods.csv').open(encoding='utf-8',newline='') as f:
                rows=[v for v in csv.DictReader(f) if v['group']==group and v['scenario']=='shock' and int(v['trace'])==2]
            assert len(rows)==600 and len({(v['period'],v['node']) for v in rows})==600
            for v in rows:
                assert int(v['demand'])==int(truth[int(v['period'])-1])
                assert float(v['cost'])==int(v['inventory'])+int(v['backlog'])
            cost=sum(float(v['cost']) for v in rows)/600
            e=next(v for v in read(d/'episodes.json') if v['group']==group and v['scenario']=='shock' and v['trace']==2)
            assert abs(cost-e['cost'])<1e-10
            for stage,(lo,hi) in STAGES.items():
                sub=[v for v in rows if lo<=int(v['period'])<=hi]
                total=sum(float(v['cost']) for v in sub)
                stages.append(dict(seed=seed,method=method,stage=stage,period_start=lo,period_end=hi,
                                   mean_cost=total/len(sub),overall_contribution=total/600))
                execution.append(dict(seed=seed,method=method,stage=stage,node_periods=len(sub),
                                      actual_corrections=sum(int(v['actual_order'])!=int(v['policy_order']) for v in sub)))
            scores=[v for v in read(d/'scores.json') if v['group']==group and v['trace']==2]
            periods=[v['decision_period'] for v in scores if v.get('generation_event')]
            assert periods==[68,73,78,83]
            generation.append(dict(seed=seed,method=method,generation_periods=periods,second_peak_new_llm_events=0))
            for score in scores:
                p=score['decision_period'];samples=np.asarray(score['forecasts'],dtype=float)
                assert samples.shape[0:2]==(2,3)
                samples=samples.reshape(6,-1);h=samples.shape[1];y=truth[p-1:p-1+h]
                assert len(y)==h
                mae=abs(samples.mean(0)-y)
                crps=abs(samples-y).mean(0)-.5*abs(samples[:,None,:]-samples[None,:,:]).mean((0,1))
                for j in range(h):
                    forecast_points.append(dict(seed=seed,method=method,decision_period=p,target_period=p+j,
                        actual=float(y[j]),forecast_mean=float(samples[:,j].mean()),mae=float(mae[j]),crps=float(crps[j])))
    cost_summary=[]
    for stage in STAGES:
        values={m:statistics.mean(x['mean_cost'] for x in stages if x['stage']==stage and x['method']==m) for m in ('merton','sundial')}
        contributions={m:statistics.mean(x['overall_contribution'] for x in stages if x['stage']==stage and x['method']==m) for m in ('merton','sundial')}
        cost_summary.append(dict(stage=stage,**values,delta=values['sundial']-values['merton'],
            change_pct=100*(values['sundial']/values['merton']-1),overall_delta_contribution=contributions['sundial']-contributions['merton']))
    subsets={'first_peak_during':lambda x:66<=x['decision_period']<=85 and 66<=x['target_period']<=85,
             'second_peak_before':lambda x:x['decision_period']<106 and 106<=x['target_period']<=125,
             'second_peak_during':lambda x:106<=x['decision_period']<=125 and 106<=x['target_period']<=125}
    quality=[]
    for subset,predicate in subsets.items():
        for method in ('merton','sundial'):
            sub=[x for x in forecast_points if x['method']==method and predicate(x)]
            quality.append(dict(subset=subset,method=method,overlapping_forecast_points=len(sub),
                mae=statistics.mean(x['mae'] for x in sub),crps=statistics.mean(x['crps'] for x in sub)))
    assert abs(sum(x['overall_delta_contribution'] for x in cost_summary)-(24.114-25.015666666666668))<1e-10
    for p,h in inputs.items():assert sha(Path(p))==h
    write(OUT/'input_hashes.json',inputs);write(OUT/'stage_costs.json',stages);write(OUT/'execution.json',execution)
    write(OUT/'generation.json',generation);write(OUT/'forecast_points.json',forecast_points)
    write(OUT/'summary.json',dict(cost_stages=cost_summary,forecast_quality=quality,api=0,
        forecasts_regenerated=False,post_hoc=True,one_physical_double_path=True,new_rule_limit=6,old_rule_limit=4))
    lines=['# 双峰场景机制诊断：六条Sundial与四条Merton','','仅读取已保存五模型原始记录，API0、无新预测、无参数/规则变更。','事后诊断，不是预先登记的机制因果实验。实际双峰第66—85/106—125期。','','## 分阶段平均I+B成本','','|阶段|Merton|Sundial|变化|对200期总体成本差的贡献|','|---|---:|---:|---:|---:|']
    for v in cost_summary:lines.append(f"|{LABELS[v['stage']]}|{v['merton']:.6f}|{v['sundial']:.6f}|{v['change_pct']:+.3f}%|{v['overall_delta_contribution']:+.6f}|")
    lines+=['','各阶段均值的分母是该阶段期数×3节点，不等同整回合25.015667/24.114；最后列可加总为-0.901667。','第二峰4/5模型当期成本改善（seed13退化），第一峰3退化/2持平；第二峰后4改善/1退化。','库存/在途/策略状态跨阶段延续，分阶段差异不是该阶段预测的独立因果贡献。','','## 已保存六条部署预测的误差','','MAE为六条预测均值对真实需求的绝对误差；经验CRPS同时评估六样本的分布，越低越好。','按相同决策时点、真实目标期匹配。预测窗口重叠；Merton样本在不同模型seed间可重复，不能把点数当独立样本。','','|范围|方法|重叠预测点数|MAE|CRPS|','|---|---|---:|---:|---:|']
    for q in quality:lines.append(f"|{q['subset']}|{q['method']}|{q['overlapping_forecast_points']}|{q['mae']:.6f}|{q['crps']:.6f}|")
    lines+=['','第二峰前发出的预测仅评价其覆盖的第二峰目标期；覆盖决策为88/93/98/103期。','模型可见首峰及部分回落历史，但未知第二峰真实时间/幅度。第一峰前没有预测记录（首次通知第68期），不能做第一峰提前预警对比。','','## 判断与限制','','LLM生成时点两方法五模型均68/73/78/83，第二峰没有生成新规则；会继续使用更新预测筛选已有候选池。','结果与“第二峰预测更准、第二峰及后续成本更低”解释相符。','但不能证明Transformer识别周期：仅一次双峰物理路径，无前缀删减/时间扰乱/注意力干预，','Sundial包含适配器与最新报告响应，6/4规则上限不同且LLM随机回复不同。','第二峰预测改善也可能由近期报告跟随、预训练先验、样本分布或适配器产生；两个峰不构成稳定周期。','不能声称周期识别为已证实机制，或将预测误差改善单独因果归因于最终成本。','全部五模型和阶段保留，不筛出有利模型。源记录SHA前后核对一致。']
    report=ROOT/'docs/2026-10-15-sundial-double-mechanism-diagnosis.md';report.write_bytes(('\n'.join(lines)+'\n').encode())
    package=ROOT/'docs/artifacts/sundial_double_mechanism_diagnosis_v1';package.mkdir()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as e:key=winreg.QueryValueEx(e,'DEEPSEEK_API_KEY')[0].encode()
    manifest={}
    for i,p in enumerate([p for p in OUT.rglob('*') if p.is_file()]+[report,Path(__file__)]):
        raw=p.read_bytes();assert key not in raw;dest=package/f'{i:03}.gz';dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
        manifest[dest.name]=dict(source=str(p),raw_sha256=hashlib.sha256(raw).hexdigest(),gzip_sha256=sha(dest))
    write(package/'manifest.json',dict(files=manifest,credential_absent=True,lossless=True,api=0,source_records_unchanged=True))
    print(json.dumps(dict(cost=cost_summary,quality=quality,archived=len(manifest)),ensure_ascii=False))
if __name__=='__main__':run()
