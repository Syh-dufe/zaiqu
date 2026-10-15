"""Cost-only report and lossless no-LLM development archive."""
import csv,gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_deterministic_cost/v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 done=read(OUT/'completed.json');assert done==dict(episodes=12,rows=7200,api=0,seeds=[14,15])
 for p,s in read(OUT/'registration.json')['files'].items():assert digest(Path(p))==s,p
 summary=read(OUT/'summary.json');assert len(summary)==12
 for seed in (14,15):
  d=OUT/'runs'/f'seed{seed}_double';assert read(d/'independent_audit.json')['status']=='passed'
  with (d/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
  assert len(rows)==3600
  for e in [e for e in summary if e['seed']==seed]:
   costs=[int(x['inventory'])+int(x['backlog']) for x in rows if x['group']==e['method'] and x['scenario']==e['scenario']]
   assert len(costs)==600 and abs(sum(costs)/600-e['cost'])<1e-10
 text='''# 无LLM的Sundial/Merton订货成本开发比较

用户选择保留冻结HAPPO和统一确定性筛选器。全部方法使用已有
deterministic_search：27种网格候选、6次邻域细化、3+3搜索与独立复核路径、
20期影子滚动、5期修正、4次构造事件；没有调用或重放LLM。
本次与旧guard_pool的生成机制不同，因此不把历史LLM成绩混入本表。

三预测器：原Merton、原生Sundial、冻结multiscale24适配Sundial。
冻结HAPPO14和15号种子；同一条已使用的双峰物理需求路径trace2，
两段需求乘1.5并截断20，正常与冲击共12回合7200节点期。API0。
主指标是完整200期、3节点库存持有与欠货成本I+B的平均值，越低越好。

|模型种子|Merton|原生Sundial|新适配Sundial|新适配较Merton变化|
|---|---:|---:|---:|---:|
'''
 means={m:[] for m in ('original_merton','native_sundial','adapted_sundial')}
 for seed in (14,15):
  v={x['method']:x['cost'] for x in summary if x['seed']==seed and x['scenario']=='shock'}
  for m in means:means[m].append(v[m])
  text+=f"|{seed}|{v['original_merton']:.6f}|{v['native_sundial']:.6f}|{v['adapted_sundial']:.6f}|{100*(v['adapted_sundial']/v['original_merton']-1):+.2f}%|\n"
 means={m:sum(v)/2 for m,v in means.items()};change=100*(means['adapted_sundial']/means['original_merton']-1)
 text+=f"|两种子均值|{means['original_merton']:.6f}|{means['native_sundial']:.6f}|{means['adapted_sundial']:.6f}|{change:+.2f}%|\n"
 text+='\n新适配总体成本'+('降低' if change<0 else '增加')+f'{abs(change):.2f}%。全部种子和不利结果完整保留。\n'
 text+='''
## 核验与解释范围

逐期重算I+B、全部唯一节点期身份、正常及通知前HAPPO动作逐值复现、
模型参数hash不变、需求索引、报告可见时点和API0均通过。
正常场景不触发修正，三方法成本相同。
这些结果只说明固定确定性订货器下预测模块的闭环成本，不能直接代表
实时LLM系统的效果。两个模型种子共享一条已暴露物理需求路径，不能称
两个独立场景、独立确认或总体统计显著性。额外计算为Sundial推断时间，
筛选与影子模拟预算在三个方法间相同。大预训练权重仅本地保留，公开固定
revision及参数SHA；本归档不包含这些大权重。
'''
 report=ROOT/'docs/2026-10-15-sundial-deterministic-cost-results.md';report.write_text(text,encoding='utf-8')
 target=ROOT/'docs/artifacts/sundial_deterministic_cost_completed_v1';assert not target.exists();target.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=[p for p in OUT.rglob('*') if p.is_file()]+list((ROOT/'experiments/sundial_deterministic_cost').glob('*.py'))+[Path(__file__),report,ROOT/'docs/superpowers/plans/2026-10-15-sundial-deterministic-cost.md']
 entries={}
 for i,p in enumerate(files):
  raw=p.read_bytes();assert key not in raw;dest=target/'files'/f'{i:03d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 (target/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,api=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print('COST_ARCHIVED',len(entries),means,change)
if __name__=='__main__':main()
