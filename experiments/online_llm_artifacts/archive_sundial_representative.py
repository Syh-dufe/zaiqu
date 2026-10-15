"""Independent raw-cost verification and lossless diagnosis/modification export."""
import csv,gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_representative_paths'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source(seed):return ROOT/(f'results/sundial_closed_loop_development/development_v2/runs/batch01_seed{seed}' if seed<13 else f'results/sundial_focus_completion/v1/runs/seed{seed}_two_types')
def main():
 pairs=[];n=0
 for seed in range(11,16):
  directory=OUT/f'no_api_replay_v1/seed{seed}';v=read(directory/'replay_verification.json');assert v['status']=='passed' and v['network_requests']==0
  registration=read(directory/'registration.json')
  for p,sha in {**registration['implementation_sha256'],**registration['reused_sha256']}.items():assert digest(Path(p))==sha
  for p,sha in registration['source_sha256'].items():assert digest(ROOT/p)==sha
  done=read(directory/'completed.json');expected=read(source(seed)/'completed.json')['parameter_checks']['adapted_sundial']['before']
  assert done['parameter_checks']['adapted_sundial']['before']==done['parameter_checks']['adapted_sundial']['after']==expected
  with (directory/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
  assert len(rows)==2400 and len({(r['scenario'],r['trace'],r['period'],r['node']) for r in rows})==2400
  episodes=read(directory/'episodes.json');assert len(episodes)==4
  for e in episodes:
   local=[r for r in rows if r['scenario']==e['scenario'] and int(r['trace'])==e['trace']];assert len(local)==600
   assert all(float(r['cost'])==int(r['inventory'])+int(r['backlog']) for r in local)
   assert abs(sum(float(r['cost']) for r in local)/600-e['cost'])<1e-12;n+=1
  old=read(source(seed)/'episodes.json')
  for trace in (2,3):
   def cost(values,group):return next(e['cost'] for e in values if e['group']==group and e['trace']==trace and e['scenario']=='shock')
   a=cost(old,'adapted_sundial');b=cost(episodes,'adapted_sundial');m=cost(old,'original_merton')
   pairs.append(dict(seed=seed,trace=trace,type='double_surge' if trace==2 else 'surge_then_drop',merton_cost=m,old_sundial_cost=a,new_fixed_reply_cost=b,reduction_vs_old_percent=100*(a-b)/a))
  for r in read(directory/'scores.json'):
   audit=r['forecast_audit']['prediction'];indices=audit['path_selection']['indices'];paths=audit['diagnostic_paths']
   assert r['forecasts']==[[paths[i] for i in indices[:3]],[paths[i] for i in indices[3:]]]
   assert all(i<16 for i in indices[:3]) and all(i>=16 for i in indices[3:])
 assert n==20
 types={}
 for trace in (2,3):
  local=[p for p in pairs if p['trace']==trace];old=sum(p['old_sundial_cost'] for p in local)/5;new=sum(p['new_fixed_reply_cost'] for p in local)/5;merton=sum(p['merton_cost'] for p in local)/5
  types[local[0]['type']]=dict(merton_cost=merton,old_cost=old,new_cost=new,reduction_vs_old_percent=100*(old-new)/old,reduction_vs_merton_percent=100*(merton-new)/merton,improved=sum(p['new_fixed_reply_cost']<p['old_sundial_cost'] for p in local),tied=sum(p['new_fixed_reply_cost']==p['old_sundial_cost'] for p in local),worse=sum(p['new_fixed_reply_cost']>p['old_sundial_cost'] for p in local))
 summary=dict(pairs=pairs,type_means=types,verified_episodes=20,node_periods=12000,network_requests=0,not_live_api_confirmation=True,old_llm_replies_fixed=True)
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 text='''# 双峰退化诊断与代表路径筛选开发结果

## 1. 双峰退化证据

原五模型双峰成本：Merton21.02200、修正Sundial21.68033，seed14/15分别退化12.095%/20.119%。两系统第一峰/间隔期在seed14成本逐值一致，首次实际动作差在110期；seed15从73期分歧。seed14的阶段平均成本（旧/修正）为：106–125期45.4667/46.1167；126–150期21.8400/29.0800；151–175期8.3733/14.4933；176–200期11.6667/19.7733。seed15在86–105期为14.6333/32.1167，已在两峰间形成较大状态差。

同状态、同候选的跨预测器复算将两项影响分开：

- seed15第73期的Merton候选，在Sundial搜索/复核组预测的20期总成本收益分别−65.67/+277.33；在真实未来事后分支为+667。该规则未出现在当时Sundial候选池中；Sundial当时三个候选在六路径上的成本评分均相同，真实未来分支收益均仅+24。这支持“候选差异与小样本筛选不稳定并存”，不能单独归因Sundial均值误差。
- seed14第108期，在两个仍相同的实际状态上，Merton已执行候选的真实未来分支收益+122，但Sundial搜索/复核估计−11.67/−29.67。该规则同样不在Sundial池内。
- seed14第128期，在Sundial自己的状态上，其实际加订规则真实未来分支收益+560。恢复期全程成本较高，不等于这次加订本身有害，不能据此设置恢复期禁加订规则。

上述收益是固定五期修正、其后回到冻结策略的20期影子分支总I+B，正值表示低于同状态零修正。它们不是全回合平均成本或完备因果归因；真实未来仅为事后标签，没有进入控制器。分支中后续重选行为与真实完整控制器不同。

此外，原适配器会放大块分布：seed15第73期原始块标准差均值1.056→适配后3.526；第108期1.165→3.554。两组各只使用前三条路径，搜索和复核可有较大排序差。放大是否失准尚未证明；原模型以外的分布适配/候选生成问题没有被本次修改解决。

## 2. 修改内容

用户批准分层代表路径方案：在每组16条已生成路径内部按总需求排序，固定分5/6/5条三层，用未来5/10/20期平均需求特征选择最接近层中心的原路径，各取一条。搜索与复核独立，不混用，保持3+3评分、原样本/适配器/HAPPO/提示/调用预算不变。没有新增训练或引入Merton到Sundial预测支路。

五模型两类缓存共265次预测的成员、确定性、数组不变和分组隔离检查通过。5/6/5层等权评分是有损近似，不保证保留完整分布、极端尾部或峰形；不保证降低成本。

## 3. API0的固定回复闭环重放

冻结旧生成/修订回复，在相同需求与五模型上重放新路径选择，20回合、12000节点期。状态与反馈会变化，而LLM回复没有重新生成，故以下只是控制变量开发结果，不是新机制真实API闭环或独立确认。

|场景|seed|Merton旧成本|原修正Sundial|代表路径重放|相对原修正降低%|
|---|---:|---:|---:|---:|---:|
'''
 for p in pairs:text+=f"|{p['type']}|{p['seed']}|{p['merton_cost']:.6f}|{p['old_sundial_cost']:.6f}|{p['new_fixed_reply_cost']:.6f}|{p['reduction_vs_old_percent']:.3f}|\n"
 text+='\n|场景|原修正均值|新重放均值|相对原修正降低%|改善/持平/退化|\n|---|---:|---:|---:|---|\n'
 for kind,v in types.items():text+=f"|{kind}|{v['old_cost']:.6f}|{v['new_cost']:.6f}|{v['reduction_vs_old_percent']:.3f}|{v['improved']}/{v['tied']}/{v['worse']}|\n"
 text+='''
## 4. 核验、限制与处置

两退化模型原诊断重放16回合已完成，初次收尾因Replay缺records字段异常；保留原日志、失败时脚本和原始文件。独立逐值比对9600节点期及8个同状态探针通过，不把原驱动尾段称成功。脚本字段已修复，既有数值无需再仿真。

新重放全部20回合逐期成本独立复算、正常/通知前匹配、冻结HAPPO参数前后与原模型hash匹配、旧输入文件及实现源码hash核验通过。原完整模型大权重只本地保留，公开源码/路径/哈希。API0；记录内历史token/回复是复用，不计新费用。两类各一条已暴露需求路径，五模型不是五条独立需求；不计算泛化显著性、不按结果筛seed。固定分层参数不随结果再调，未启动付费批。
'''
 report=ROOT/'docs/2026-10-15-sundial-double-diagnosis-and-representative-results.md';report.write_text(text,encoding='utf-8')
 target=ROOT/'docs/artifacts/sundial_double_diagnosis_representative_v1';assert not target.exists();target.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=list(OUT.rglob('*'))+list((ROOT/'results/sundial_double_diagnosis/v1').rglob('*'))
 files += list((ROOT/'experiments/sundial_representative_paths').glob('*.py'))+[Path(__file__),ROOT/'experiments/online_llm_artifacts/diagnose_sundial_double.py',report,ROOT/'docs/superpowers/specs/2026-10-15-sundial-representative-paths-design.md',ROOT/'docs/superpowers/plans/2026-10-15-sundial-representative-paths.md']
 files += list((ROOT/'results').glob('sundial_double_diagnosis_seed*.log'))+list((ROOT/'results').glob('sundial_representative_replay_seed*.log'))
 entries={}
 for i,p in enumerate(p for p in files if p.is_file()):
  raw=p.read_bytes();assert key not in raw;dest=target/'files'/f'{i:04d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 (target/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,network_requests=0,original_diagnosis_tail_failure_kept=True,not_live_api_confirmation=True),ensure_ascii=False,indent=2),encoding='utf-8')
 print('REPRESENTATIVE_INDEPENDENT_COST_AUDIT_AND_LOSSLESS_EXPORT',n,len(entries),types)
if __name__=='__main__':main()
