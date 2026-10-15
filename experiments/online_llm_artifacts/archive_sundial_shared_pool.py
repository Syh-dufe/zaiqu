"""Matched-pool diagnostic evaluation; never report oracle branches as live cost."""
import gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_shared_pool_diagnosis/v1'
PROVIDERS=('original_merton','adapted_sundial','crps24','multiscale24')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def eligible(v,z):return v['valid'] and z['valid'] and v['cost']<=.99*z['cost'] and v['downstream']<=z['downstream']
def main():
 for p,sha in read(OUT/'freeze.json')['sha256'].items():assert digest(p)==sha,p
 rows=[];seen={};duplicates=0;branch_count=0
 for seed in (14,15):
  folder=OUT/f'seed{seed}';assert read(folder/'verification.json')['status']=='passed'
  probes=read(folder/'matched_state_probes.json');assert len(probes)==4
  for p in probes:
   candidates=p['candidates'];assert len(candidates)==7 and candidates[0]['id']=='zero' and p['labels_never_used_by_controller']
   for c in candidates:
    assert set(c['scores'])==set(PROVIDERS)|{'retrospective_true_future'}
    assert all(s['valid'] for provider in PROVIDERS for s in c['scores'][provider]) and c['scores']['retrospective_true_future']['valid']
   branch_count+=7*(4*6+1)
   key=(seed,p['state_sha256']);duplicate=key in seen
   if duplicate:
    assert p['candidates']==seen[key]['candidates'];duplicates+=1
   else:seen[key]=p
   hindsight=[c['scores']['retrospective_true_future']['cost'] for c in candidates];best=min(hindsight);zero=hindsight[0]
   result=dict(seed=seed,period=p['decision_period'],state_owner=p['state_owner'],state_sha256=p['state_sha256'],duplicate_state=duplicate,providers={})
   for provider in PROVIDERS:
    search=[c['scores'][provider][0] for c in candidates];review=[c['scores'][provider][1] for c in candidates]
    accepted=sorted((i for i in range(1,7) if eligible(search[i],search[0])),key=lambda i:(search[i]['cost'],i))
    chosen=next((i for i in accepted if eligible(review[i],review[0])),0)
    result['providers'][provider]=dict(chosen=candidates[chosen]['id'],retrospective_total_cost=hindsight[chosen],gain_vs_zero=zero-hindsight[chosen],pool_oracle_regret=hindsight[chosen]-best,harmful=hindsight[chosen]>zero)
   rows.append(result)
 assert branch_count==1400 and len(rows)==8
 unique=[r for r in rows if not r['duplicate_state']];assert len(unique)==6 and duplicates==2
 overall={p:dict(mean_regret=sum(r['providers'][p]['pool_oracle_regret'] for r in unique)/len(unique),mean_gain_vs_zero=sum(r['providers'][p]['gain_vs_zero'] for r in unique)/len(unique),harmful_choices=sum(r['providers'][p]['harmful'] for r in unique)) for p in PROVIDERS}
 gate=overall['multiscale24']['mean_regret']<overall['adapted_sundial']['mean_regret'] and overall['multiscale24']['harmful_choices']<=overall['adapted_sundial']['harmful_choices']
 summary=dict(states=8,unique_states=6,duplicate_states=2,independent_demand_paths=1,model_seeds=[14,15],diagnostic_branches=branch_count,old_replay_node_periods=9600,api=0,overall=overall,rows=rows,gate_passed=gate,not_live_api_cost=True,post_selected_diagnosis=True)
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 text='''# 再训练适配器的固定候选池诊断

本阶段API0；两个已暴露模型×一条双峰物理需求路径，8记录去重为6状态，不是独立需求样本。固定同一状态、同一联合7候选池和原3+3评分规则，比较四预测器。真实未来仅为事后20期影子分支标签，未进入训练、预测、筛选或提示；不是完整真实API闭环成本。

## 去重状态汇总

|预测器|平均池内事后regret|平均相对zero收益|有害选择数|
|---|---:|---:|---:|
'''
 for p,v in overall.items():text+=f"|{p}|{v['mean_regret']:.6f}|{v['mean_gain_vs_zero']:.6f}|{v['harmful_choices']}|\n"
 text+=f"\n事前继续门槛通过：{gate}。multiscale24仍为主方法，crps24是消融，不按成绩替换主方法。regret是相同状态中所选规则的事后总I+B减去本候选池事后最优值；越小越好。这不是全回合平均成本或泛化显著性。\n"
 text+='\n## 各去重状态\n\n|seed|时期|状态来源|旧24所选|新多尺度所选|旧regret|新regret|\n|---|---:|---|---|---|---:|---:|\n'
 for r in unique:
  a=r['providers']['adapted_sundial'];b=r['providers']['multiscale24'];text+=f"|{r['seed']}|{r['period']}|{r['state_owner']}|{a['chosen']}|{b['chosen']}|{a['pool_oracle_regret']:.3f}|{b['pool_oracle_regret']:.3f}|\n"
 text+='\n## 限制与处置\n\n联合7候选池是控制变量诊断池，超过原部署zero+3池，且可能含等价规则；所有方法共享，不能直接当部署成绩。重放原16回合9600节点期逐值一致，恢复真实旧状态；1400诊断影子分支不包含恢复状态时原控制器自身的评分计算。两个首次分歧前状态重复已排除。候选池真实未来最优只用于评价，不会部署。原源/权重/输入hash保持、网络0。\n'
 text+=('该局部诊断支持另行登记小型真实API开发，但尚未证明新机制降低运行成本；本次未启动付费批。' if gate else '未通过固定门槛，本轮版本收尾归档，不继续调整阈值、选择种子或追加付费批。')+'\n'
 report=ROOT/'docs/2026-10-15-sundial-shared-pool-results.md';report.write_text(text,encoding='utf-8')
 target=ROOT/'docs/artifacts/sundial_shared_pool_completed_v1';assert not target.exists();target.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=[p for p in OUT.rglob('*') if p.is_file()]+list((ROOT/'experiments/sundial_shared_pool_diagnosis').glob('*.py'))+[Path(__file__),report,ROOT/'docs/superpowers/plans/2026-10-15-sundial-shared-pool-diagnosis.md']
 entries={}
 for i,p in enumerate(files):
  raw=p.read_bytes();assert key not in raw;dest=target/'files'/f'{i:03d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 (target/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,api=0,not_live_api_cost=True),ensure_ascii=False,indent=2),encoding='utf-8')
 print('SHARED_POOL_SUMMARY_AND_ARCHIVE',len(entries),gate,overall)
if __name__=='__main__':main()
