"""Preserve the service-outage cost attempt without treating fallback as LLM evidence."""
import gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_multiscale_cost/v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert read(OUT/'progress.json')['status']=='blocked_service_outage'
 calls=[c for p in (OUT/'runs').rglob('calls.json') for c in read(p)]
 assert len(calls)==6
 report=ROOT/'docs/2026-10-15-multiscale-cost-service-outage.md'
 report.write_text('''# 新适配Sundial真实API成本实验：服务故障记录

登记提交a98406f，原计划14、15号模型的双峰正常/冲击共4回合。
启动前余额可用。官方故障证据保存在原结果根，记录查询时点而非
声称目前仍在故障。官方事件：https://status.deepseek.com/incidents/7116348214287。

14号完成2回合，但4次生成请求全部30秒超时，完全回退；正常成本21.455、
冲击25.660不能代表有效LLM机制成绩。15号正常回合完成，冲击回合中断；
该任务2次请求含1次超时、1次中断时仍为started。总计6次已发起请求，
5次超时和1次在途请求；服务端可能处理请求，未知用量不能记为零费用。
没有有效的完整实时LLM比较。所有原始请求、日志、故障状态、部分产物保留。

原批锁定停留在blocked_service_outage，不覆盖、不盲重启。随后用户选择
冻结HAPPO加统一确定性筛选进行无API预测模块成本比较，另目录登记运行；
它不等同于本次失败的实时LLM实验。原已完成历史真实API成绩不受影响。
''',encoding='utf-8')
 target=ROOT/'docs/artifacts/sundial_multiscale_cost_outage_v1';assert not target.exists();target.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=[p for p in OUT.rglob('*') if p.is_file()]+[report,Path(__file__)]
 entries={}
 for i,p in enumerate(files):
  raw=p.read_bytes();assert key not in raw
  dest=target/'files'/f'{i:03d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 (target/'manifest.json').write_text(json.dumps(dict(files=entries,credential_absent=True,lossless=True,attempted_http=6,valid_live_llm_comparisons=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print('OUTAGE_ARCHIVED',len(entries))
if __name__=='__main__':main()
