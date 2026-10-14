"""Export complete adapter trial, including curve and all unfavorable cases."""
import gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_adapter_development/v1';TARGET=ROOT/'docs/artifacts/sundial_adapter_development_v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
assert read(OUT/'completed.json')['case_methods']==480 and not TARGET.exists()
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
files=[p for p in OUT.glob('*') if p.is_file()]+list((ROOT/'experiments/sundial_adapter_development').glob('*.py'))
files += [ROOT/'docs/superpowers/specs/2026-10-14-sundial-adapter-design.md',ROOT/'docs/superpowers/plans/2026-10-14-sundial-adapter.md',Path(__file__)]
files += list((ROOT/'results').glob('sundial_adapter_*v1.log'))
TARGET.mkdir(parents=True);entries={}
for i,p in enumerate(dict.fromkeys(files)):
 blob=p.read_bytes();assert key not in blob
 dest=TARGET/'files'/f'{i:04d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(blob,mtime=0));assert gzip.decompress(dest.read_bytes())==blob
 entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=hashlib.sha256(blob).hexdigest(),gzip_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
(TARGET/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,all_curves_negative_cases_kept=True,checkpoint_weights_local_only=True),ensure_ascii=False,indent=2),encoding='utf-8')
metrics=read(OUT/'metrics.json');text=(OUT/'report.md').read_text(encoding='utf-8')
text+='\n## 各类型与所有不利路径\n\n|类型|原Sundial CRPS|适配Sundial CRPS|Merton CRPS|最新值CRPS|\n|---|---:|---:|---:|---:|\n'
for kind in sorted({p['type'] for p in metrics['paths']}):
 row=[]
 for m in ('sundial','adapted','merton','naive'):row.append(sum(p['means'][m]['crps'] for p in metrics['paths'] if p['type']==kind)/5)
 text+='|'+kind+'|'+ '|'.join(f'{v:.6f}' for v in row)+'|\n'
negative={m:sum(p['means']['adapted']['crps']>p['means'][m]['crps'] for p in metrics['paths']) for m in ('sundial','merton','naive')}
text+=f'\n20验证路径中适配方案CRPS高于参照的数量：{negative}。旧试用失败不覆盖，不改变旧门槛。本结果仅输出适配的预测证据，没有实际订货成本或LLM语义贡献结果。\n'
(ROOT/'docs/2026-10-14-sundial-adapter-results.md').write_text(text,encoding='utf-8')
print('ADAPTER_LOSSLESS_EXPORT',len(entries))
