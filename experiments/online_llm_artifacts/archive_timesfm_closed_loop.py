"""Publish the completed negative development batch without altering frozen sources."""
import csv,gzip,hashlib,json,math,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/timesfm_closed_loop_development/development_v1'
TARGET=ROOT/'docs/artifacts/timesfm_closed_loop_development_v1_completed'
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
import winreg
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
done=read(OUT/'completed.json');summary=read(OUT/'summary.json');assert len(done['completed_tasks'])==10 and not summary['fixed_gate_passed']
episodes=[];rows_count=0;calls=[];scores=[];runtime=[]
for task in done['completed_tasks']:
 d=OUT/'runs'/task['label'];audit=read(d/'audit.json')
 assert digest(d/'audit.json')==task['audit_sha256'] and audit['status']=='passed'
 for name,sha in audit['raw_sha256'].items():assert digest(d/name)==sha
 with (d/'periods.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
 assert len(rows)==len({(r['group'],r['scenario'],r['trace'],r['period'],r['node']) for r in rows})==19200
 rows_count+=len(rows)
 for e in read(d/'episodes.json'):
  local=[r for r in rows if r['group']==e['group'] and r['scenario']==e['scenario'] and int(r['trace'])==e['trace']]
  assert len(local)==600 and all(float(r['cost'])==int(r['inventory'])+int(r['backlog']) for r in local)
  assert math.isclose(e['cost'],sum(float(r['cost']) for r in local)/600,abs_tol=1e-9)
  episodes.append(e)
 calls+=read(d/'calls.json');scores+=read(d/'scores.json');runtime+=read(d/'runtime_failures.json')
assert len(episodes)==320 and rows_count==192000 and len(calls)==summary['http']
for m,v in summary['shock_means'].items():assert math.isclose(v['cost'],sum(e['cost'] for e in episodes if e['group']==m and e['scenario']=='shock')/40,abs_tol=1e-9)
diagnosis=dict(episodes=320,node_periods=192000,http=len(calls),semantic=sum(c.get('attempt')==1 for c in calls),
 format_failures=sum(c.get('failure_kind')=='format' for c in calls),http_failures=sum(c.get('failure_kind')=='http' for c in calls),
 fatal_http=sum(c.get('failure') in ('HTTP_401','HTTP_402','HTTP_403') for c in calls),execution_fallbacks=len(runtime),
 generation_failures=sum(r.get('failure')=='generation_failed' for r in scores),revision_failures=sum(r.get('revision_failed') is True for r in scores),
 first_repair_requests=sum(c.get('attempt')==2 for c in calls),all_attempts=read(OUT/'attempts.json'),
 pair_cost_worse={m:sum(p['cost_differences'][m]>0 for p in summary['pairs']) for m in ('original_merton','center_merton','center_naive')},
 cost_means={m:v['cost'] for m,v in summary['shock_means'].items()},type_costs={t:{m:v['cost'] for m,v in values.items()} for t,values in summary['type_means'].items()},
 seed_costs={s:{m:v['cost'] for m,v in values.items()} for s,values in summary['seed_means'].items()},
 fixed_gate_passed=False,usage=summary['usage'],not_independent_confirmation=True,api_response_randomness_disclosed=True)
for p,sha in read(OUT/'freeze.json')['source_sha256'].items():assert digest(ROOT/p)==sha
for p,sha in read(OUT/'freeze.json')['dependencies'].items():assert digest(p)==sha
archive=OUT/'archive';manifest=read(archive/'manifest.json')
for relative,e in manifest['files'].items():
 p=archive/relative;assert digest(p)==e['gzip_sha256']
 blob=gzip.decompress(p.read_bytes());assert hashlib.sha256(blob).hexdigest()==e['source_sha256'] and key not in blob
assert not TARGET.exists(),'Preserve completed publication'
TARGET.mkdir(parents=True);files={};origins={}
for relative,e in manifest['files'].items():
 src=archive/relative;dest=TARGET/'files'/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(src.read_bytes())
 name=dest.relative_to(ROOT).as_posix();files[name]=digest(dest);origins[name]=e
write(TARGET/'diagnosis.json',diagnosis)
write(TARGET/'manifest.json',dict(files=files,origins=origins,lossless=True,credential_absent=True,all_attempts_preserved=True,large_model_weights_public_revision_sha_only=True))
lines=['# TimesFM闭环开发：完整结果与归档','','320回合、192000唯一节点期，10任务全部审核通过。五seed11..15、batch01/06已暴露开发输入，无训练。','','|方案|冲击平均成本↓|','|---|---:|']
for m,v in diagnosis['cost_means'].items():lines.append(f'|{m}|{v:.6f}|')
lines+=['','## 四类冲击成本','','|类型|原Merton|Merton中心|最新值中心|TimesFM中心|','|---|---:|---:|---:|---:|']
for t,v in diagnosis['type_costs'].items():lines.append('|'+t+'|'+ '|'.join(f'{v[m]:.6f}' for m in ('original_merton','center_merton','center_naive','center_timesfm'))+'|')
lines+=['','## 全部种子','','|种子|原Merton|Merton中心|最新值中心|TimesFM中心|','|---|---:|---:|---:|---:|']
for s,v in diagnosis['seed_costs'].items():lines.append('|'+s+'|'+ '|'.join(f'{v[m]:.6f}' for m in ('original_merton','center_merton','center_naive','center_timesfm'))+'|')
lines+=['','## 开销与边界','',f"HTTP {diagnosis['http']}；语义请求{diagnosis['semantic']}；总tokens {summary['usage']['total_tokens']}。格式不合法响应{diagnosis['format_failures']}，格式修复请求{diagnosis['first_repair_requests']}，初始生成最终失败{diagnosis['generation_failures']}，修订最终失败{diagnosis['revision_failures']}，执行回退{diagnosis['execution_fallbacks']}；fatal HTTP {diagnosis['fatal_http']}。全部attempt与原始记录保留。",f"TimesFM成本高于参照的40配对数量：{diagnosis['pair_cost_worse']}。",'','预登记开发门槛未通过，不启动该版本独立确认。TimesFM比Merton均值中心新路径低约0.52%，比原Merton高约0.09%，比最新值中心高约0.39%；不是全面改善。','预测试用误差降低与本次闭环成本并非同一结论；原因尚未通过因果消融确定。可能涉及路径构造、截断、评价窗口、规则敏感性及API随机回复，不能把假设当成已证实原因。','四组LLM均重新现场调用，API回复随机；每类只有2独立需求路径，模型重复不是独立需求，不称显著或未见泛化。最新值最低是开发结果，不能据此直接宣布新最优方法。','原SYSTEM与提示未改，仍含历史Merton预测描述；新组实际forecast provider明示于forecast_audit，不声称提示准确描述了新技术。','逐期成本、唯一身份、模型/源码/预测路径/规则执行与报告因果通过审核；所有原始记录已无损gzip并核对SHA。公开模型revision及SHA，925MB TimesFM权重仅本地，不称GitHub含权重。']
(ROOT/'docs/2026-10-14-timesfm-closed-loop-development-results.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
write(OUT/'final_independent_verification.json',dict(episodes=320,node_periods=192000,raw_costs_recomputed=True,archive_entries=len(files),source_model_dependencies_verified=True,credential_absent=True))
print(json.dumps(dict(archive_entries=len(files),diagnosis=diagnosis),ensure_ascii=False))
