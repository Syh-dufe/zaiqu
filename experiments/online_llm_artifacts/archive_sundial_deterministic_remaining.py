"""Archive all remaining outcomes and combine the four exposed shock paths."""
import csv,gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_deterministic_remaining/v1'
METHODS=('original_merton','native_sundial','adapted_sundial')
NAMES=('单次突增','持续突增','双峰冲击','突增后下降')
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 done=read(OUT/'completed.json');assert done['episodes']==60 and done['rows']==36000 and done['api']==0 and len(done['tasks'])==10
 for p,s in read(OUT/'registration.json')['files'].items():assert digest(Path(p))==s,p
 summary=read(OUT/'summary.json');assert len(summary)==60
 for task in done['tasks']:
  seed,trace=task['seed'],task['trace'];d=OUT/'runs'/f'seed{seed}_trace{trace}'
  assert read(d/'independent_audit.json')['status']=='passed' and read(d/'calls.json')==[]
  with (d/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
  assert len(rows)==3600 and len({tuple(x[k] for k in ('group','scenario','trace','period','node')) for x in rows})==3600
  for e in [e for e in summary if e['seed']==seed and e['trace']==trace]:
   costs=[int(x['inventory'])+int(x['backlog']) for x in rows if x['group']==e['method'] and x['scenario']==e['scenario']]
   assert len(costs)==600 and abs(sum(costs)/600-e['cost'])<1e-10
 # Check previously published bytes before reusing double/drop summaries.
 for name in ('sundial_deterministic_extension_completed_v1','sundial_deterministic_drop_completed_v1'):
  for v in read(ROOT/'docs/artifacts'/name/'manifest.json')['files'].values():
   if Path(v['source']).name in ('summary.json','combined_five_seed_summary.json'):assert digest(Path(v['source']))==v['source_sha256']
 double=read(ROOT/'results/sundial_deterministic_extension/v1/combined_five_seed_summary.json')['all_episodes']
 drop=read(ROOT/'results/sundial_deterministic_drop/v1/summary.json')
 combined=summary+[dict(e,trace=2,type='double_surge') for e in double]+[dict(e,trace=3,type='surge_then_drop') for e in drop]
 assert len(combined)==120
 text='''# 无LLM确定性订货器：单次/持续突增补齐及四类场景汇总

新增两个已暴露物理路径，保持原HAPPO11..15正常best、原Merton、原生Sundial、
multiscale24和已有确定性搜索器不变，无训练、LLM API或旧回复重放。
新增60回合36000节点期，10串行任务；合并此前双峰和突增后下降共120回合
72000节点期。每类一条物理需求路径，五个模型不等于五条独立需求路径。

## 新增两类逐种子完整200期平均I+B成本

|场景|模型种子|Merton|原生Sundial|新适配Sundial|新适配较Merton|
|---|---|---:|---:|---:|---:|
'''
 for trace in (0,1):
  for seed in range(11,16):
   v={e['method']:e['cost'] for e in summary if e['trace']==trace and e['seed']==seed and e['scenario']=='shock'}
   text+=f"|{NAMES[trace]}|{seed}|{v[METHODS[0]]:.6f}|{v[METHODS[1]]:.6f}|{v[METHODS[2]]:.6f}|{100*(v[METHODS[2]]/v[METHODS[0]]-1):+.2f}%|\n"
 text+='\n## 四场景各五模型均值\n\n|场景|Merton|原生Sundial|新适配Sundial|新适配较Merton|改善模型数|\n|---|---:|---:|---:|---:|---:|\n'
 means={};counts={}
 for trace in range(4):
  means[trace]={m:sum(e['cost'] for e in combined if e['trace']==trace and e['method']==m and e['scenario']=='shock')/5 for m in METHODS}
  count=0
  for seed in range(11,16):
   v={e['method']:e['cost'] for e in combined if e['trace']==trace and e['seed']==seed and e['scenario']=='shock'};count+=v[METHODS[2]]<v[METHODS[0]]
  v=means[trace];counts[trace]=count
  text+=f"|{NAMES[trace]}|{v[METHODS[0]]:.6f}|{v[METHODS[1]]:.6f}|{v[METHODS[2]]:.6f}|{100*(v[METHODS[2]]/v[METHODS[0]]-1):+.2f}%|{count}/5|\n"
 overall={m:sum(v[m] for v in means.values())/4 for m in METHODS}
 text+=f"|四类型等权均值|{overall[METHODS[0]]:.6f}|{overall[METHODS[1]]:.6f}|{overall[METHODS[2]]:.6f}|{100*(overall[METHODS[2]]/overall[METHODS[0]]-1):+.2f}%|—|\n"
 text+='''
## 核验和解释范围

新增36000行独立重算I+B及唯一身份、每回合600节点期和均值；需求逐期索引、
模型/源文件hash、报告可见时点、动作0..20、无网络和无权重更新通过。
正常/通知前实际动作必须等于HAPPO proposal且zero修正、三方法逐值一致，
另保留每方法normal/shock前缀检查。未声称复现不存在的13..15历史trace0/1
缓存。负面结果全部保留，不按结果选模型或调整参数。

单次突增沿用trace0原区间乘1.5；持续突增沿用trace1较长区间乘1.25，
需求向上取整并截断20。通知仅一次，原四构造事件、后续筛选和5期修正
全部不变，持续期不能解释成全程都有新候选构造。
每类只有一条暴露Poisson需求路径，没有未见确认、统计显著性或现实数据
验证；跨类型均值仅描述这四条路径等权，不代表现实场景频率。
固定确定性订货器结果不能代替实时LLM系统成绩。Sundial大权重仅本地，
公开revision与参数SHA，不声称已放入Git归档。
'''
 report=ROOT/'docs/2026-10-15-sundial-deterministic-four-scenario-results.md';report.write_text(text,encoding='utf-8')
 (OUT/'four_scenario_summary.json').write_text(json.dumps(dict(api=0,episodes=120,rows=72000,means=means,overall=overall,improved_counts=counts,all_episodes=combined),indent=2),encoding='utf-8')
 target=ROOT/'docs/artifacts/sundial_deterministic_remaining_completed_v1';assert not target.exists();target.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=[p for p in OUT.rglob('*') if p.is_file()]+list((ROOT/'experiments/sundial_deterministic_remaining').glob('*.py'))+[Path(__file__),report,ROOT/'docs/superpowers/plans/2026-10-15-sundial-deterministic-remaining.md']
 entries={}
 for i,p in enumerate(files):
  raw=p.read_bytes();assert key not in raw;dest=target/'files'/f'{i:03d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 (target/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,api=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print('FOUR_SCENARIO_ARCHIVED',len(entries),means,overall)
if __name__=='__main__':main()
