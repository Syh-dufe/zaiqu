"""Combine all five models, preserve all development outcomes without seed selection."""
import csv,gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_deterministic_extension/v1';OLD=ROOT/'results/sundial_deterministic_cost/v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert read(OUT/'completed.json')==dict(episodes=18,rows=10800,api=0,seeds=[11,12,13])
 for p,s in read(OUT/'registration.json')['files'].items():assert digest(Path(p))==s,p
 # Previously published archive binds all14/15 results before this extension.
 old_manifest=read(ROOT/'docs/artifacts/sundial_deterministic_cost_completed_v1/manifest.json')
 for v in old_manifest['files'].values():
  if str(OLD) in v['source']:assert digest(Path(v['source']))==v['source_sha256']
 summary=read(OUT/'summary.json')+read(OLD/'summary.json');assert len(summary)==30
 for seed in range(11,16):
  directory=(OUT if seed<=13 else OLD)/'runs'/f'seed{seed}_double'
  assert read(directory/'independent_audit.json')['status']=='passed' and read(directory/'calls.json')==[]
  with (directory/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
  assert len(rows)==3600 and len({tuple(x[k] for k in ('group','scenario','trace','period','node')) for x in rows})==3600
  for e in [v for v in summary if v['seed']==seed]:
   costs=[int(x['inventory'])+int(x['backlog']) for x in rows if x['group']==e['method'] and x['scenario']==e['scenario']]
   assert len(costs)==600 and abs(sum(costs)/600-e['cost'])<1e-10
 text='''# 无LLM订货成本：五个模型种子的完整双峰开发比较

按用户要求补齐11、12、13，复用已完成14、15的全部结果，不重跑或筛选种子。
新增18回合10800节点期；合计30回合18000节点期，API0，无模型训练。
三方法均保留相同冻结HAPPO，采用既有确定性搜索与独立复核，只替换预测器。
网格(-2,0,2)^3、6次邻域细化、3+3预测路径、20期影子滚动、5期修正均相同。
新适配固定multiscale24，不以成绩改选crps24，也不采用失败的代表路径筛选。

## 双峰冲击完整200期平均成本

|模型种子|Merton|原生Sundial|新适配Sundial|新适配对Merton|
|---|---:|---:|---:|---:|
'''
 totals={m:[] for m in ('original_merton','native_sundial','adapted_sundial')};improved=0
 for seed in range(11,16):
  v={e['method']:e['cost'] for e in summary if e['seed']==seed and e['scenario']=='shock'}
  for m in totals:totals[m].append(v[m])
  change=100*(v['adapted_sundial']/v['original_merton']-1);improved+=change<0
  text+=f"|{seed}|{v['original_merton']:.6f}|{v['native_sundial']:.6f}|{v['adapted_sundial']:.6f}|{change:+.2f}%|\n"
 means={m:sum(v)/5 for m,v in totals.items()};change=100*(means['adapted_sundial']/means['original_merton']-1)
 text+=f"|五种子均值|{means['original_merton']:.6f}|{means['native_sundial']:.6f}|{means['adapted_sundial']:.6f}|{change:+.2f}%|\n"
 text+=f'\n新适配较Merton均值变化{change:+.2f}%，{improved}/5模型种子成本降低；其余结果全部保留。\n'
 text+='''
## 完整性与边界

成本按逐期库存持有与欠货I+B、3节点×200期取平均；独立重算18000行身份与均值。
正常场景不触发修正，三方法相同；正常及通知前HAPPO动作、报告可见时点、
模型hash不变和网络0由原逐期审核通过。预测器和规则都不读取真实未来。

五个模型种子共享同一条已暴露双峰物理需求路径trace2，不能当五条独立路径，
不作总体统计显著性或未见路径确认。双峰是两段需求乘1.5再截断20，背景为
Poisson合成需求。这里只比较固定确定性订货器下的预测模块，不代表实时LLM
完整机制的效果，也不将旧LLM候选生成成绩混入本表。所有不利结果均公开。
大预训练权重仅本地，公开revision与参数SHA；归档不包含这些大权重。
'''
 report=ROOT/'docs/2026-10-15-sundial-deterministic-five-seed-results.md';report.write_text(text,encoding='utf-8')
 (OUT/'combined_five_seed_summary.json').write_text(json.dumps(dict(episodes=30,rows=18000,api=0,means=means,change_percent=change,improved_seeds=improved,all_episodes=summary),indent=2),encoding='utf-8')
 target=ROOT/'docs/artifacts/sundial_deterministic_extension_completed_v1';assert not target.exists();target.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=[p for p in OUT.rglob('*') if p.is_file()]+list((ROOT/'experiments/sundial_deterministic_extension').glob('*.py'))+[Path(__file__),report,ROOT/'docs/superpowers/plans/2026-10-15-sundial-deterministic-extension.md',OLD/'summary.json',ROOT/'docs/artifacts/sundial_deterministic_cost_completed_v1/manifest.json']
 entries={}
 for i,p in enumerate(files):
  raw=p.read_bytes();assert key not in raw;dest=target/'files'/f'{i:03d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 (target/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,api=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print('FIVE_SEED_COST_ARCHIVED',len(entries),means,change,improved)
if __name__=='__main__':main()
