"""Original full raw/causal/DSL audits scoped to one trace and new float64 adapter."""
import inspect,csv
from pathlib import Path
def audit(runner,directory,data,expected_hash,offline=False):
 references=[]
 for s in (14,15):
  root=runner.ROOT/f'results/sundial_focus_completion/v1/runs/seed{s}_two_types'
  if runner.core.read(root/'completed.json')['parameter_checks']['adapted_sundial']['before']==expected_hash:references.append(root)
 assert len(references)==1
 with (references[0]/'periods.csv').open(encoding='utf-8',newline='') as stream:
  reference_rows={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in csv.DictReader(stream) if r['group']=='original_merton' and int(r['trace'])==2}
 old=runner.module('multiscale_cost_original_audit',runner.ROOT/'experiments/sundial_closed_loop_development/audit.py');text=inspect.getsource(old.audit)
 marker='text=inspect.getsource(legacy.audit);needle=';assert text.count(marker)==1
 replacement="text=inspect.getsource(legacy.audit)\n for before,after,count in [('range(4)','SELECTED',1),('len(methods)*8','len(methods)*2',2),('len(methods)*1600','len(methods)*400',1)]:\n  assert text.count(before)==count,before\n  text=text.replace(before,after)\n needle="
 text=text.replace(marker,replacement)
 assert text.count('ns=dict(legacy.__dict__);exec')==1;text=text.replace('ns=dict(legacy.__dict__);exec','ns=dict(legacy.__dict__,SELECTED=SELECTED);exec')
 assert text.count('for trace in range(4):')==1;text=text.replace('for trace in range(4):','for trace in SELECTED:')
 assert text.count("raw=np.asarray(v['raw_blocks'])")==1;text=text.replace("raw=np.asarray(v['raw_blocks'])","raw=np.asarray(v['raw_blocks'],dtype=np.float64)")
 marker=" row_map={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in rows}";assert text.count(marker)==1;text=text.replace(marker,marker+'\n row_map.update(REFERENCE_ROWS)')
 ns=dict(old.__dict__,SELECTED=runner.SELECTED,REFERENCE_ROWS=reference_rows);exec(compile(text,str(Path(__file__)),'exec'),ns);result=ns['audit'](runner,directory,data,expected_hash,offline)
 seed=runner.core.read(Path(directory)/'protocol.json')['seed'] if 'seed' in runner.core.read(Path(directory)/'protocol.json') else None
 # The exact model hash, rather than a guessed metadata seed field, identifies the source.
 with (references[0]/'periods.csv').open(encoding='utf-8',newline='') as f:oldrows={(r['scenario'],r['trace'],r['period'],r['node']):r for r in csv.DictReader(f) if r['group']=='adapted_sundial'}
 with (Path(directory)/'periods.csv').open(encoding='utf-8',newline='') as f:
  for r in csv.DictReader(f):
   if r['scenario']=='base' or int(r['period'])<data['events'][2]['start_index']+3:
    a=oldrows[r['scenario'],r['trace'],r['period'],r['node']];assert all(r[k]==a[k] for k in ('demand','cost','inventory','backlog','actual_order','policy_order'))
 result.update(actual_variant='multiscale24',adapter_dtype='float64',selected_traces=[2],historical_normal_pre_notice_exact=True)
 runner.core.write(Path(directory)/'audit.json',result);return result
