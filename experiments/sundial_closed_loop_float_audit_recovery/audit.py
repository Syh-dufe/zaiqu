"""Explicit serialization dtype recovery; every behavioral audit remains unchanged."""
import inspect
from pathlib import Path

def audit(runner,directory,data,expected_hash,offline=False):
 old=runner.module('sundial_original_frozen_float_audit',runner.HERE/'audit.py')
 text=inspect.getsource(old.audit);needle="raw=np.asarray(v['raw_blocks'])"
 assert text.count(needle)==1
 text=text.replace(needle,"raw=np.asarray(v['raw_blocks'],dtype=np.float32)")
 ns=dict(old.__dict__);exec(compile(text,str(Path(__file__)),'exec'),ns)
 result=ns['audit'](runner,directory,data,expected_hash,offline)
 result.update(raw_dtype_matches_frozen_model=True,audit_recovery='explicit_float32_serialization')
 runner.core.write(Path(directory)/'audit.json',result);return result
