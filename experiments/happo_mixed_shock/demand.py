"""Mixed demand only: no changes to inventory, policy, reward or information."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'results/happo_mixed_shock/formal_v1'
TYPES = ('normal', 'single', 'sustained', 'double', 'drop')

def digest_trace(values):
    return hashlib.sha256(json.dumps(list(map(int,values)),separators=(',',':')).encode()).hexdigest()

def sample(kind):
    from envs.generator import merton
    generator = merton(200,20)
    base = [int(generator[t]) for t in range(200)]
    parts = []
    if kind != 'normal':
        start = int(np.random.randint(50,91))
        length = int(np.random.randint(40,61) if kind=='sustained' else np.random.randint(15,26))
        factor = float(np.random.uniform(1.1,1.5) if kind=='sustained' else np.random.uniform(1.2,1.8))
        parts.append([start,start+length,factor])
        if kind == 'double':
            second = start+length+int(np.random.randint(20,36))
            parts.append([second,second+int(np.random.randint(15,26)),float(np.random.uniform(1.2,1.8))])
        elif kind == 'drop':
            second = start+length
            parts.append([second,second+int(np.random.randint(30,51)),float(np.random.uniform(.3,.8))])
    actual = base.copy()
    for start,end,factor in parts:
        assert 0 <= start < end <= 200
        for t in range(start,end):
            actual[t] = min(20,int(np.ceil(base[t]*factor))) if factor>1 else int(np.floor(base[t]*factor))
    return dict(type=kind,base=base,demand=actual,intervals=parts)

def install(seed, ledger=None):
    sys.path.insert(0,str(ROOT/'external/liu-inventory'))
    from envs import serial
    validation = json.loads((OUT/'validation.json').read_text(encoding='utf-8'))
    excluded = {digest_trace(r['demand']) for r in validation['records']}
    counter = 0
    def training():
        nonlocal counter
        kind = TYPES[int(np.random.randint(0,5))]
        for _ in range(10000):
            row = sample(kind)
            if digest_trace(row['demand']) not in excluded: break
        else: raise RuntimeError('Training/validation collision exhaustion')
        counter += 1
        if ledger is not None:
            with ledger.open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(dict(seed=seed,ordinal=counter,**row),separators=(',',':'))+'\n')
        return row['demand']
    def evaluation():
        return len(validation['records']), [r['demand'].copy() for r in validation['records']]
    serial.get_training_data = training
    serial.get_eval_data = evaluation
    return validation
