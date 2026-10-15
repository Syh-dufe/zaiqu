"""Keep paid partial work stopped when user requests cached historical controls."""
import gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_response_live_api/development_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert read(OUT/'progress.json')['status']=='stopped_for_user_requested_cached_comparison'
 calls=[c for p in (OUT/'runs').rglob('calls.json') for c in read(p)];counts={k:sum(c['status']==k for c in calls) for k in ('valid','failed','started')}
 report=ROOT/'docs/2026-10-15-response-live-newpath-pilot-stopped.md'
 report.write_text(f'''# 新路径真实API批按用户修正停止

原e29c15a以reserved adapter-dev新成本路径比较Merton与响应Sundial。
用户要求直接复用历史Merton结果，故停止驱动和子进程，不再派发。
共{len(calls)}次已发起HTTP，状态{counts}；中断时在途请求可能由服务端处理，
未知usage不能记为免费。原始calls、部分episodes、日志、进程快照和注册保留。
没有完整32回合结果，也没有新Sundial成绩；不覆盖或盲重启该根。

后续另登记旧stationary四类路径，仅跑响应Sundial；完整匹配四类且旧审核通过
的是11/12号，Merton只读复用。成本作为开发比较，历史API失败/回退和时点差异
披露，不按成绩筛种子。此批开销与新批128HTTP64语义预算分列。\n''',encoding='utf-8')
 target=ROOT/'docs/artifacts/response_live_newpath_user_stopped_v1';assert not target.exists();target.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=[p for p in OUT.rglob('*') if p.is_file()]+[Path(__file__),report];entries={}
 for i,p in enumerate(files):
  raw=p.read_bytes();assert key not in raw;dest=target/f'{i:03d}.gz';dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=sha(p),gzip_sha256=sha(dest))
 (target/'manifest.json').write_bytes(json.dumps(dict(files=entries,lossless=True,credential_absent=True,attempted_http=len(calls),counts=counts),indent=2).encode());print('SCOPE_STOP_ARCHIVED',len(entries),len(calls),counts)
if __name__=='__main__':main()
