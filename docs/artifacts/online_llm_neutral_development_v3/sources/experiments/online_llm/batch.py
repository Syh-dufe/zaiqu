"""Register4 fresh development traces, preflight, then run2 frozen seeds once."""
import argparse
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
from run import ROOT,UPSTREAM,LIBRARY,METHODS,read,write,digest,training,validate_inputs,contracts,source_hashes


def used_inputs(exclude):
    used=set();sources=[]
    for parent in (ROOT/'results',ROOT/'docs/artifacts'):
        for path in parent.rglob('*.json'):
            if path.is_relative_to(exclude):
                continue
            try:
                data=read(path)
            except (ValueError,OSError):
                continue
            if not isinstance(data,dict):
                continue
            count=0
            for key in ('base','shock'):
                values=data.get(key,[])
                if not isinstance(values,list):
                    continue
                for trace in values:
                    if isinstance(trace,list) and len(trace)>=200 and all(type(v) in (int,float) for v in trace[:200]):
                        used.add(tuple(trace[:200]));count+=1
            if count:
                sources.append(dict(path=str(path),sha256=digest(path),traces=count))
    return used,sources


def generate():
    import numpy as np
    sys.path.insert(0,str(UPSTREAM))
    from envs.generator import merton
    np.random.seed(20270801)
    base=[merton(200,20).demand_list for _ in range(4)]
    rng=random.Random(20270802)
    events=[dict(start_index=rng.randint(60,100),duration=rng.randint(20,40),intensity=intensity) for intensity in (1.25,1.25,1.5,1.5)]
    shock=[[min(20,math.ceil(e['intensity']*v)) if e['start_index']<=i<e['start_index']+e['duration'] else v for i,v in enumerate(trace)] for trace,e in zip(base,events)]
    return validate_inputs(dict(demand_seed=20270801,event_seed=20270802,base=base,shock=shock,events=events))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/online_llm/development_v1')
    parser.add_argument('--operator-library',type=Path,default=LIBRARY)
    parser.add_argument('--preflight',action='store_true',help='Register immutable inputs/contracts; no HTTP or evaluation')
    opts=parser.parse_args();out=opts.output.resolve();library=opts.operator_library.resolve()
    if not os.environ.get('DEEPSEEK_API_KEY'):
        raise RuntimeError('DEEPSEEK_API_KEY missing')
    if not out.exists():
        data=generate()
        used,prior=used_inputs(out)
        signatures=[tuple(t[:200]) for key in ('base','shock') for t in data[key]]
        if any(t in used for t in signatures):
            raise RuntimeError('Registered demand collision; preserve registration seed, do not selectively regenerate')
        unchanged_shocks=[i for i,(base,shock) in enumerate(zip(data['base'],data['shock'])) if base[:200]==shock[:200]]
        out.mkdir(parents=True)
        write(out/'inputs.json',data)
        try:
            audits={str(seed):contracts(out/'inputs.json',library,training(seed)) for seed in (11,12)}
            frozen=source_hashes()
            sources=out/'sources';sources.mkdir()
            for rel in frozen:
                path=sources/rel;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,path)
            write(out/'manifest.json',dict(status='registered',development_only=True,training_seeds=[11,12],methods=list(METHODS),
                episodes=80,demand_seed=20270801,event_seed=20270802,intensities=[1.25,1.25,1.5,1.5],
                input_sha256=digest(out/'inputs.json'),library_path=str(library),library_sha256=digest(library),
                unchanged_shock_indices=unchanged_shocks,
                unchanged_shock_note='Clipping may leave a registered shock identical to its own baseline; all fixed traces retained',
                collision_diagnosis_reference=str(ROOT/'results/online_llm/preflight_v1_collision_diagnosis.json'),
                source_sha256=frozen,contracts=audits,prior_input_sources=prior,
                max_http_requests_batch=160,random_seed_rule='20270803 +100*trace + event_index1..4',
                screening='Every5 periods following notification, including after generation budget exhausted',
                random_comparator='Matched to online_feedback initial and replacement scoring;4 events; constant-vector diagnostic',
                revision='One replacement of candidate0, retain3; only search feedback; no review feedback',
                notification='After2 completed event periods; no true start/intensity/duration in prompt',
                real_world_deadline_guaranteed=False))
        except Exception as exc:
            write(out/'failed_registration.json',dict(failure=str(exc)[:1000]));raise
    manifest=read(out/'manifest.json')
    if manifest['status']!='registered' or (out/'launch.json').exists() or (out/'failed.json').exists() or (out/'completed.json').exists():
        raise RuntimeError('Batch already launched or failed; inspect preserved outputs')
    def check_registered():
        if source_hashes()!=manifest['source_sha256'] or digest(library)!=manifest['library_sha256'] or digest(out/'inputs.json')!=manifest['input_sha256']:
            raise RuntimeError('Frozen source/library/input changed since registration')
        validate_inputs(read(out/'inputs.json'))
        for seed in (11,12):
            if contracts(out/'inputs.json',library,training(seed))!=manifest['contracts'][str(seed)]:
                raise RuntimeError('Preflight model/source contracts changed')
    check_registered()
    if opts.preflight:
        print('PREFLIGHT_OK no API or evaluation',str(out),flush=True);return
    # Exclusive launch marker prevents concurrent or repeated launches.
    with (out/'launch.json').open('x',encoding='utf-8') as stream:
        import json
        json.dump(dict(pid=os.getpid(),started=time.time(),manifest_sha256=digest(out/'manifest.json')),stream,indent=2)
    try:
        for seed in (11,12):
            check_registered()
            label=f'seed{seed}'
            write(out/'progress.json',dict(status='evaluating',seed=seed,pid=os.getpid()))
            command=[sys.executable,'-u',str(Path(__file__).with_name('run.py')),'--run-name',label,
                '--input-file',str(out/'inputs.json'),'--training-directory',str(training(seed)),
                '--operator-library',str(library),'--output-root',str(out)]
            with (out/f'{label}.log').open('x',encoding='utf-8') as stream:
                result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f'{label} failed; see preserved log and calls')
            check_registered()
            protocol=read(out/label/'protocol.json')
            for key,value in manifest['contracts'][str(seed)].items():
                if protocol.get(key)!=value:
                    raise RuntimeError(f'{label} child contract differs from registration: {key}')
        check_registered()
        from analyze import analyze
        summary=analyze(out,require_complete=True)
        check_registered()
        write(out/'completed.json',dict(status='completed',episodes=80,summary=summary,development_only=True))
        write(out/'progress.json',dict(status='completed',pid=os.getpid()))
    except Exception as exc:
        # Analyze partial outputs without dropping failed or unfavorable episodes.
        write(out/'failed.json',dict(failure=str(exc)[:1000],partial_outputs_preserved=True))
        from analyze import analyze
        analysis_failure=None
        try:
            analyze(out)
        except Exception as error:
            analysis_failure=str(error)[:1000]
        if analysis_failure:
            write(out/'analysis_failed.json',dict(failure=analysis_failure))
        raise


if __name__=='__main__':
    main()
