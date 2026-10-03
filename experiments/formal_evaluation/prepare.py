"""Register all stage A demands before any policy is evaluated."""
import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path
import numpy as np
from inputs import validate_batch

ROOT=Path(__file__).resolve().parents[2]


def write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if out.exists(): parser.error('Refuse overwrite')
    seeds=set(range(20261201,20261211));checked=0;duplicates=[]
    previous_sequences=set()
    for parent in (ROOT/'results',ROOT/'docs/artifacts'):
        historical=set(parent.rglob('demands.json')) | set(parent.rglob('batch*.json'))
        for file in historical:
            data=json.loads(file.read_text(encoding='utf-8-sig'));checked+=1
            if not isinstance(data,dict) or 'base' not in data: continue
            if any(data.get(k) in seeds for k in ('demand_seed','event_seed')): duplicates.append(str(file))
            for trace in data.get('base',[]):previous_sequences.add(tuple(trace[:200]))
    if duplicates:raise RuntimeError('Registered seed already used: '+repr(duplicates))
    sys.path.insert(0,str(ROOT/'external/liu-inventory'))
    from envs.generator import merton
    # Compute all batches before saving, and before any model can be loaded.
    batches=[];seen=set()
    for number in range(1,6):
        ds=20261199+2*number;es=ds+1
        np.random.seed(ds);base=[merton(200,20).demand_list for _ in range(4)]
        rng=random.Random(es)
        events=[dict(start_index=rng.randint(60,100),duration=rng.randint(20,40)) for _ in base]
        shock=[[min(20,math.ceil(1.5*d)) if e['start_index']<=i<e['start_index']+e['duration'] else d
                for i,d in enumerate(trace)] for trace,e in zip(base,events)]
        data=validate_batch(dict(demand_seed=ds,event_seed=es,base=base,shock=shock,events=events),4)
        for trace in base:
            signature=tuple(trace[:200])
            if signature in previous_sequences or signature in seen:raise RuntimeError('Repeated demand path: stop before evaluating')
            seen.add(signature)
        stats=[]
        for trace,changed,e in zip(base,shock,events):
            indices=range(e['start_index'],e['start_index']+e['duration'])
            total=sum(trace[i] for i in indices);after=sum(changed[i] for i in indices)
            stats.append(dict(base_total=total,shock_total=after,actual_relative_increase=after/total-1 if total else None,
                              capped_periods=sum(math.ceil(1.5*trace[i])>20 for i in indices),duration=e['duration']))
        data['shock_statistics']=stats;batches.append(data)
    out.mkdir(parents=True)
    records=[]
    for i,data in enumerate(batches,1):
        path=out/f'batch{i}.json';write(path,data)
        records.append(dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cases=4,
                            demand_seed=data['demand_seed'],event_seed=data['event_seed']))
    protocol=ROOT/'docs/2026-10-03-formal-experiment-protocol.md'
    write(out/'manifest.json',dict(protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest(),
        history_search=dict(roots=['results','docs/artifacts'],demand_files_checked=checked,prior_unique_traces=len(previous_sequences),
                            seeds_previously_used=[],duplicate_paths=0),batches=records,source_length=201,consumed_indices=[0,199]))
    print('PREPARED',len(records),'batches, 20 unique unseen demand paths; previous files:',checked,flush=True)


if __name__=='__main__':main()
