"""Scope changed explicitly; numerical, causal and behavioral checks retained."""
import inspect
from pathlib import Path
def audit(runner,directory,data,expected_hash,offline=False):
 old=runner.module('focus_immutable_full_audit',runner.ROOT/'experiments/sundial_closed_loop_development/audit.py');text=inspect.getsource(old.audit)
 marker='text=inspect.getsource(legacy.audit);needle='
 assert text.count(marker)==1
 replacement="text=inspect.getsource(legacy.audit)\n for before,after,count in [('range(4)','SELECTED',1),('len(methods)*8','len(methods)*4',2),('len(methods)*1600','len(methods)*800',1)]:\n  assert text.count(before)==count,before\n  text=text.replace(before,after)\n needle="
 text=text.replace(marker,replacement)
 assert text.count('ns=dict(legacy.__dict__);exec')==1;text=text.replace('ns=dict(legacy.__dict__);exec','ns=dict(legacy.__dict__,SELECTED=SELECTED);exec')
 assert text.count('for trace in range(4):')==1;text=text.replace('for trace in range(4):','for trace in SELECTED:')
 assert text.count("raw=np.asarray(v['raw_blocks'])")==1;text=text.replace("raw=np.asarray(v['raw_blocks'])","raw=np.asarray(v['raw_blocks'],dtype=np.float32)")
 ns=dict(old.__dict__,SELECTED=runner.SELECTED);exec(compile(text,str(Path(__file__)),'exec'),ns)
 result=ns['audit'](runner,directory,data,expected_hash,offline);result.update(selected_traces=list(runner.SELECTED),raw_float32=True)
 runner.core.write(Path(directory)/'audit.json',result);return result
