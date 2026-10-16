"""Explicit cache-source correction; frozen v1 and its failed attempt stay intact."""
import argparse,importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
s=importlib.util.spec_from_file_location('fixed_base_stock_frozen_v1',ROOT/'experiments/sundial_fixed_base_stock/batch.py')
base=importlib.util.module_from_spec(s);sys.modules[s.name]=base;s.loader.exec_module(base)
FAILED=ROOT/'results/sundial_fixed_base_stock/v1'
PLAN=ROOT/'docs/superpowers/plans/2026-10-16-sundial-fixed-base-stock-source-recovery.md'
base.OUT=ROOT/'results/sundial_fixed_base_stock/v2'
refs=base.references
def references():
 values=refs()
 for v in values:
  if v['method']=='happo':v['path']=str(ROOT/f'results/submission_required/v1/runs/confirmation01_main_seed{v["seed"]}')
 return values
base.references=references
sources=base.sources
def source_hashes():
 values=sources()
 for p in [HERE/'batch.py',PLAN]+[p for p in FAILED.iterdir() if p.is_file()]:values[str(p)]=base.sha(p)
 return values
base.sources=source_hashes
archive=base.archive
def archive_v2(directory,files):
 directory=directory.with_name(directory.name.replace('_v1','_v2'))
 extras=[HERE/'batch.py',PLAN]+[p for p in FAILED.iterdir() if p.is_file()]
 return archive(directory,files+extras)
base.archive=archive_v2
def preflight():
 data=base.read(base.INPUT);values=base.cached_costs(dict(references=references()),data)
 assert len(values)==90
 print('CORRECTED_CACHED_COSTS_RECOMPUTED',len(values),flush=True)
 return values
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=('preflight','register','run','verify','check-publication'));a=p.parse_args()
 if a.action=='preflight':preflight()
 elif a.action=='register':preflight();base.register()
 elif a.action=='check-publication':base.check_publication(base.OUT/'completed_publication.json')
 else:{'run':base.run,'verify':base.verify}[a.action]()
