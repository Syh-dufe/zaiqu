"""Mixed demand only: no changes to inventory, policy, reward or information."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'results/happo_matched_shock/formal_v2'
TYPES = ('normal', 'single', 'sustained', 'double', 'drop')

def digest_trace(values):
    return hashlib.sha256(json.dumps(list(map(int,values)),separators=(',',':')).encode()).hexdigest()

TIMING_OFFSETS = tuple(range(-10,10,2))
TEST_INPUTS = ROOT/'results/joint_baseline_confirmation/confirmation_v1/inputs'

def protected_test_traces():
    files=sorted(TEST_INPUTS.glob('batch*.json'))
    if len(files)!=10: raise RuntimeError('Expected ten original test batches')
    hashes=set()
    for path in files:
        data=json.loads(path.read_text(encoding='utf-8'))
        for key in ('base','shock'):
            for trace in data[key]: hashes.add(digest_trace(trace))
    if len(hashes)!=80: raise RuntimeError('Expected 80 original base/shock demand paths')
    return hashes,files

def sample(kind,offset=None):
    from envs.generator import merton
    generator=merton(200,20)
    base=[int(generator[t]) for t in range(200)]
    if offset is None: offset=int(np.random.choice(TIMING_OFFSETS))
    profiles={
        'normal':[],
        'single':[(80+offset,100+offset,1.5)],
        'sustained':[(70+offset,120+offset,1.25)],
        'double':[(75+offset,95+offset,1.5),(115+offset,135+offset,1.5)],
        'drop':[(80+offset,100+offset,1.5),(100+offset,140+offset,.5)],
    }
    parts=profiles[kind]
    actual=base.copy()
    for start,end,factor in parts:
        assert 0<=start<end<=200
        for t in range(start,end):
            actual[t]=min(20,int(np.ceil(base[t]*factor))) if factor>1 else int(np.floor(base[t]*factor))
    return dict(type=kind,base=base,demand=actual,intervals=parts,timing_offset=offset)

def install(seed, ledger=None):
    sys.path.insert(0,str(ROOT/'external/liu-inventory'))
    from envs import serial
    validation = json.loads((OUT/'validation.json').read_text(encoding='utf-8'))
    excluded,_ = protected_test_traces()
    excluded.update(digest_trace(r[key]) for r in validation['records'] for key in ('base','demand'))
    counter = 0
    def training():
        nonlocal counter
        kind = TYPES[int(np.random.randint(0,5))]
        for _ in range(10000):
            row = sample(kind)
            if not ({digest_trace(row['base']),digest_trace(row['demand'])} & excluded): break
        else: raise RuntimeError('Training/validation/protected-test collision exhaustion')
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
