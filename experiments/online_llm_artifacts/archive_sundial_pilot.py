"""Lossless public pilot export, checkpoint bytes retained only in local cache."""
import gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/sundial_forecast_pilot/development_v1'
TARGET=ROOT/'docs/artifacts/sundial_forecast_pilot_v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
assert read(OUT/'completed.json')['case_methods']==192 and not TARGET.exists()
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
paths=[p for p in OUT.glob('*') if p.is_file()]
paths += [p for p in (ROOT/'results/sundial_forecast_pilot/setup_v1').glob('*') if p.is_file()]
paths += list((ROOT/'experiments/sundial_forecast_pilot').glob('*.py'))
paths += [ROOT/'results/sundial_forecast_pilot_inference_v1.log',ROOT/'results/timesfm_forecast_pilot/development_v1/cases.json',ROOT/'results/timesfm_path_development/development_v1/paths.json',ROOT/'docs/superpowers/specs/2026-10-14-sundial-pilot-design.md',ROOT/'docs/superpowers/plans/2026-10-14-sundial-pilot.md',Path(__file__)]
cache=Path(read(ROOT/'results/sundial_forecast_pilot/setup_v1/download_completed.json')['cache'])
paths += [p for p in cache.glob('*') if p.is_file() and p.name!='model.safetensors']
TARGET.mkdir(parents=True);entries={}
for i,p in enumerate(dict.fromkeys(paths)):
 data=p.read_bytes();assert key not in data
 dest=TARGET/'files'/f'{i:04d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(data,mtime=0))
 assert gzip.decompress(dest.read_bytes())==data
 entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=hashlib.sha256(data).hexdigest(),gzip_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
(TARGET/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,checkpoint_local_only=True,checkpoint_revision='3212e42564493f520593e5414af4367fc4b49226'),ensure_ascii=False,indent=2),encoding='utf-8')
print('SUNDIAL_LOSSLESS_EXPORT',len(entries))
