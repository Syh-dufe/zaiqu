"""Completed expanded forecast validation export; no checkpoint binaries."""
import gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_expanded_validation/v1'
TARGET=ROOT/'docs/artifacts/sundial_expanded_validation_v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
done=read(OUT/'completed.json');assert done['method_windows']==240 and not TARGET.exists()
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
paths=[p for p in OUT.glob('*') if p.is_file()]+list((ROOT/'experiments/sundial_expanded_validation').glob('*.py'))
paths += [ROOT/'results/sundial_expanded_prepare_v1.log',ROOT/'results/sundial_expanded_inference_v1.log',ROOT/'docs/superpowers/specs/2026-10-14-sundial-expanded-design.md',ROOT/'docs/superpowers/plans/2026-10-14-sundial-expanded.md',Path(__file__)]
TARGET.mkdir(parents=True);entries={}
for i,p in enumerate(dict.fromkeys(paths)):
 data=p.read_bytes();assert key not in data
 dest=TARGET/'files'/f'{i:04d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(data,mtime=0))
 assert gzip.decompress(dest.read_bytes())==data
 entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=hashlib.sha256(data).hexdigest(),gzip_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
(TARGET/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,checkpoint_local_only=True,api=0,training=0),ensure_ascii=False,indent=2),encoding='utf-8')
text=(OUT/'report.md').read_text(encoding='utf-8')
metrics=read(OUT/'metrics.json');text+='\n## 各类型完整报告块指标\n\n|类型|Merton CRPS|Sundial CRPS|Merton MAE|Sundial MAE|\n|---|---:|---:|---:|---:|\n'
for kind,v in metrics['by_type'].items():text+=f"|{kind}|{v['merton']['block_crps']:.6f}|{v['sundial']['block_crps']:.6f}|{v['merton']['block_mae']:.6f}|{v['sundial']['block_mae']:.6f}|\n"
finish=read(OUT/'run_finished.json');text+=f"\nCPU2线程纯推理{finish['inference_seconds']:.3f}秒，加载及推理{finish['wall_seconds']:.3f}秒；不含准备/查重/审核。所有不利路径、原样本与独立指标/区间复算保留。官方128M权重仅本地，沿用原试用公开revision和SHA。\n"
(ROOT/'docs/2026-10-14-sundial-expanded-validation-results.md').write_text(text,encoding='utf-8')
print('EXPANDED_LOSSLESS_EXPORT',len(entries))
