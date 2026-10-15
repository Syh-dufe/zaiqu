"""Preserve raw registration bytes despite Git text newline normalization."""
import gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];TARGET=ROOT/'docs/artifacts/sundial_change_response_preregistration_v1'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=list(TARGET.glob('*.json'))+list((ROOT/'experiments/sundial_change_response').glob('*.py'))
 entries={};destination=TARGET/'raw_bytes';assert not destination.exists();destination.mkdir()
 for i,p in enumerate(files):
  raw=p.read_bytes();assert key not in raw;out=destination/f'{i:02d}.gz';compressed=gzip.compress(raw,mtime=0);out.write_bytes(compressed);assert gzip.decompress(compressed)==raw
  entries[out.relative_to(ROOT).as_posix()]=dict(source=str(p),raw_sha256=sha(raw),gzip_sha256=sha(compressed))
 manifest=dict(files=entries,credential_absent=True,lossless=True,reason='JSON text copies normalized CRLF to LF in Git; raw gzip is authoritative byte-preserving registration. Runtime input/source/model bytes and hashes unchanged.')
 (destination/'manifest.json').write_bytes(json.dumps(manifest,ensure_ascii=False,indent=2).encode())
 print('RESPONSE_REGISTRATION_RAW_BYTES',len(entries))
if __name__=='__main__':main()
