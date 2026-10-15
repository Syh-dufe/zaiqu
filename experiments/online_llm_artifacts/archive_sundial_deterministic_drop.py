"""Independent full-cost recomputation and complete five-model rise/drop archive."""
import csv,gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_deterministic_drop/v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert read(OUT/'completed.json')==dict(episodes=30,rows=18000,api=0,seeds=[11,12,13,14,15])
 for p,s in read(OUT/'registration.json')['files'].items():assert digest(Path(p))==s,p
 summary=read(OUT/'summary.json');assert len(summary)==30
 for seed in range(11,16):
  directory=OUT/'runs'/f'seed{seed}_drop'
  assert read(directory/'independent_audit.json')['status']=='passed' and read(directory/'calls.json')==[]
  with (directory/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
  assert len(rows)==3600 and len({tuple(x[k] for k in ('group','scenario','trace','period','node')) for x in rows})==3600
  for e in [v for v in summary if v['seed']==seed]:
   costs=[int(x['inventory'])+int(x['backlog']) for x in rows if x['group']==e['method'] and x['scenario']==e['scenario']]
   assert len(costs)==600 and abs(sum(costs)/600-e['cost'])<1e-10
 text='''# 无LLM订货成本：突增后下降五模型比较

沿用双峰实验全部冻结模型、multiscale24适配器、确定性搜索及独立复核，
只将物理输入改为stationary.json已有trace3，不以此结果修改参数。
HAPPO11..15 x Merton/原生Sundial/新适配Sundial x normal/shock，
30回合18000唯一节点期，API0，无模型训练，也不重放LLM回复。
同一条已暴露Poisson基础路径在索引[70,90)乘1.5、[90,130)乘0.5，
向上取整并截断20。报告周期3、通知延迟2期、5期修正与原预算不变。

## 完整200期冲击场景平均I+B成本

|模型种子|Merton|原生Sundial|新适配Sundial|新适配较Merton|
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
 text+=f'\n新适配较Merton总体均值变化{change:+.2f}%，{improved}/5种子成本下降，所有不利结果均保留。\n'
 text+='''
## 核验和范围

独立逐期重算I+B和全部18000行身份、每回合600节点期均值一致；模型hash
不变、正常与通知前动作复现、报告时点及需求索引、动作上限、API0均通过。
原环境在最后一个eval索引结束时清空record_act_sta，继承兼容函数再对空数组
取均值产生RuntimeWarning。该返回值是未使用的订货波动统计；本报告成本
直接来自逐期库存/欠货和reward原始行，不使用该均值。警告原日志完整保留，
未编辑冻结环境或在运行中屏蔽。全部成本行与复算须有限且一致。

与双峰一样，这仍是五个模型共享一条已暴露需求路径的开发比较，不是五条
独立场景，不能推断总体统计显著性。固定确定性订货器的结果不能替代实时
LLM完整系统成绩。大Sundial预训练权重仅本地，公开固定revision和参数SHA；
不将大权重称已包含在Git归档。先完整报告，再决定是否需要独立新路径确认。
'''
 report=ROOT/'docs/2026-10-15-sundial-deterministic-drop-results.md';report.write_text(text,encoding='utf-8')
 (OUT/'cost_summary.json').write_text(json.dumps(dict(means=means,change_percent=change,improved_seeds=improved,api=0,episodes=30,rows=18000),indent=2),encoding='utf-8')
 target=ROOT/'docs/artifacts/sundial_deterministic_drop_completed_v1';assert not target.exists();target.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=[p for p in OUT.rglob('*') if p.is_file()]+list((ROOT/'experiments/sundial_deterministic_drop').glob('*.py'))+[Path(__file__),report,ROOT/'docs/superpowers/plans/2026-10-15-sundial-deterministic-drop.md']
 entries={}
 for i,p in enumerate(files):
  raw=p.read_bytes();assert key not in raw;dest=target/'files'/f'{i:03d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 (target/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,api=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print('DROP_COST_ARCHIVED',len(entries),means,change,improved)
if __name__=='__main__':main()
