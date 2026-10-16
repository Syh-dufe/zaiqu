"""Immutable registration and local paths for the Poisson training experiment."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTHOR = ROOT / 'external' / 'liu-inventory'
OUT = ROOT / 'results' / 'poisson_optimality' / 'formal_v1'
SPEC = ROOT / 'docs/superpowers/specs/2026-10-16-poisson-optimality-design.md'
PLAN = ROOT / 'docs/superpowers/plans/2026-10-16-poisson-optimality.md'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')
    tmp.replace(path)

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def sources():
    return sorted([*AUTHOR.rglob('*.py'), *Path(__file__).parent.glob('*.py'), SPEC, PLAN])

def verify():
    manifest = read(OUT / 'freeze.json')
    for entry in manifest['files']:
        assert sha(ROOT / entry['path']) == entry['sha256'], entry['path']
    return manifest
