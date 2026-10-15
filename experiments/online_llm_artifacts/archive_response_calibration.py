"""Complete calibration provenance, raw recomputation and lossless archive."""
import csv,gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OLD=ROOT/'results/sundial_change_response/v1';OUT=ROOT/'results/sundial_change_response_recovery/v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 done=read(OUT/'completed.json');assert done['episodes']==80 and done['rows']==48000 and len(done['tasks'])==10 and done['api']==0
 for p,s in read(OUT/'registration.json')['files'].items():assert digest(Path(p))==s,p
 summary=read(OUT/'summary.json');assert len(summary)==80
 for task in done['tasks']:
  d=OLD/'runs'/f"seed{task['seed']}_{task['candidate']}";assert read(d/'independent_audit.json')['status']=='passed' and read(d/'calls.json')==[]
  with (d/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
  assert len(rows)==4800 and len({tuple(x[k] for k in ('group','scenario','trace','period','node')) for x in rows})==4800
  for e in [e for e in summary if e['seed']==task['seed'] and e['candidate']==task['candidate']]:
   costs=[int(r['inventory'])+int(r['backlog']) for r in rows if r['scenario']==e['scenario'] and int(r['trace'])==e['trace']];assert len(costs)==600 and abs(sum(costs)/600-e['cost'])<1e-10
 selection=read(OUT/'selection.json');order=read(OLD/'registration.json')['candidates'];means={c:sum(e['cost'] for e in summary if e['candidate']==c and e['scenario']=='shock')/8 for c in order}
 assert means==selection['means'];winner=min(order,key=lambda c:means[c]);assert winner==selection['winner'] and selection['gate_passed']==(winner!='zero' and means[winner]<=.99*means['zero'])
 text='''# 因果需求变化响应：成本校准阶段结果

冻结HAPPO/Sundial/multiscale24和原随机分配，仅比较5个已登记响应配置。
使用原适配器训练集首条stationary四类冲击路径、预定11/14模型，独立于之前
四条成本路径；这些仍是训练/开发路径，不是未见确认。80回合48000节点期，
API0，没有神经网络更新。未来标签仅以仿真成本用于开发选择，部署只看已送达报告。

|配置|四类两模型平均成本|
|---|---:|
'''
 for c in order:text+=f'|{c}|{means[c]:.6f}|\n'
 text+=f"\n选中{winner}，较zero成本降低{selection['cost_reduction_percent']:.4f}%，1%预设开发门槛通过。尚无五模型验证或同路径Merton比较，不声称总体优势。\n"
 text+='''
初始审核器误读不存在的horizon字段而KeyError；两零响应任务仿真完成后未审核。
独立恢复版按原min(20,201-decision_period)重建并验证全部预测路径长度，完整
复核后复用16回合，无重复仿真/API。原失败、旧stale running状态、恢复注册、
全部费用/时间与不利配置保留。其余8任务按原冻结运行器执行，响应/原适配/
分配/成本/唯一行/报告/模型hash审核通过。原始运行根和新恢复状态根分列，
以恢复根completed为准。之后用户另授权真实API开发测试，不把它冒称已经
完成先前计划的五模型无LLM验证。大Sundial权重仅本地，公开revision/SHA。
'''
 report=ROOT/'docs/2026-10-15-sundial-change-response-calibration-results.md';report.write_text(text,encoding='utf-8')
 target=ROOT/'docs/artifacts/sundial_change_response_calibration_completed_v1';assert not target.exists();target.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=[p for d in (OLD,OUT) for p in d.rglob('*') if p.is_file()]+list((ROOT/'experiments/sundial_change_response').glob('*.py'))+list((ROOT/'experiments/sundial_change_response_recovery').glob('*.py'))+[Path(__file__),report]
 entries={}
 for i,p in enumerate(files):
  raw=p.read_bytes();assert key not in raw;dest=target/f'{i:03d}.gz';dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 (target/'manifest.json').write_bytes(json.dumps(dict(files=entries,lossless=True,credential_absent=True,api=0),indent=2).encode());print('RESPONSE_CALIBRATION_ARCHIVED',len(entries),winner,means)
if __name__=='__main__':main()
