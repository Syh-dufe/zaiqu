"""Preserve user-stopped allocation experiment, including interrupted task."""
import gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_balanced_allocation/v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 progress=read(OUT/'progress.json');assert progress['status']=='stopped_by_user' and progress['no_restart']
 registration=read(OUT/'registration.json')
 for p,s in registration['files'].items():assert sha(Path(p))==s,p
 summary=read(OUT/'summary.json');n=len(progress['completed']);assert len(summary)==2*n
 for task in progress['completed']:assert read(OUT/'runs'/f"seed{task['seed']}_trace{task['trace']}"/'independent_audit.json')['status']=='passed'
 report=ROOT/'docs/2026-10-15-sundial-balanced-allocation-stopped.md'
 report.write_text(f'''# 均衡分配开发按用户要求停止

状态stopped_by_user，已完成并审核{n}/20任务、{2*n}回合、{1200*n}节点期。
中断任务{progress['interrupted_task']}的正常/冲击部分、原日志、预测和进程快照
全部保留；不把部分回合计入完整比较。API0，无训练，无覆盖或自动重启。
此前登记0ba5f7f；用户要求停止并换方法后才停，不能声称完成全部四类五种子。

已完成结果呈混合改善与退化，不采用该均衡版本。原随机分配、Sundial/HAPPO
及multiscale24权重和协议保持冻结，所有不利结果保留。下一方向先设计因果
需求变化响应适配，不读取真实场景标签或未来，不在这四条暴露测试上调到胜出。
所有原始块总量、均衡轮转、样本索引、模型hash及逐期成本审核记录保留。
大预训练权重不在此Git归档，仅本地与公开revision/SHA。\n''',encoding='utf-8')
 target=ROOT/'docs/artifacts/sundial_balanced_allocation_user_stopped_v1';assert not target.exists();target.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=[p for p in OUT.rglob('*') if p.is_file()]+list((ROOT/'experiments/sundial_balanced_allocation').glob('*.py'))+[report,Path(__file__)]
 entries={}
 for i,p in enumerate(files):
  raw=p.read_bytes();assert key not in raw;dest=target/'files'/f'{i:03d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=sha(p),gzip_sha256=sha(dest))
 (target/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,status='stopped_by_user',completed_tasks=n,api=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print('USER_STOP_ARCHIVED',n,len(entries),progress['interrupted_task'])
if __name__=='__main__':main()
