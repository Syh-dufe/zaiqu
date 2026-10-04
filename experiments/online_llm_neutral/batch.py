"""Freeze before generating neutral v3 inputs; exclusive serial development run."""
import argparse
import importlib.util
import os
from pathlib import Path
import random
import math
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
if 'neutral_v3_run_core' in sys.modules:
    CORE=sys.modules['neutral_v3_run_core']
    if Path(CORE.__file__).resolve()!=Path(__file__).with_name('run.py').resolve():
        raise RuntimeError('Neutral run alias collision')
else:
    spec=importlib.util.spec_from_file_location('neutral_v3_run_core',Path(__file__).with_name('run.py'))
    CORE=importlib.util.module_from_spec(spec);sys.modules[spec.name]=CORE;spec.loader.exec_module(CORE)
read,write,digest=CORE.read,CORE.write,CORE.digest
REFERENCE=ROOT/'docs/artifacts/online_llm_development_v1/inputs.json'


def runtime():
    import numpy as np
    import torch
    return dict(python_executable=sys.executable,python_version=sys.version,
        python_sha256=digest(Path(sys.executable)),numpy_version=np.__version__,torch_version=torch.__version__)


def previous_inputs(exclude):
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
    sys.path.insert(0,str(CORE.UPSTREAM))
    from envs.generator import merton
    np.random.seed(20271101);base=[merton(200,20).demand_list for _ in range(4)]
    rng=random.Random(20271102)
    events=[dict(start_index=rng.randint(60,100),duration=rng.randint(20,40),intensity=intensity) for intensity in (1.25,1.25,1.5,1.5)]
    shock=[[min(20,math.ceil(e['intensity']*v)) if e['start_index']<=i<e['start_index']+e['duration'] else v for i,v in enumerate(trace)] for trace,e in zip(base,events)]
    return CORE.validate_inputs(dict(demand_seed=20271101,event_seed=20271102,base=base,shock=shock,events=events))


def register(out,library):
    assert not out.exists()
    frozen=dict(phase='neutral_v3_development',source_sha256=CORE.source_hashes(),runtime=runtime(),
        reference_input_path=str(REFERENCE),reference_input_sha256=digest(REFERENCE),
        reference_model_contracts={str(seed):CORE.contracts(REFERENCE,library,CORE.training(seed)) for seed in (11,12)},
        library_path=str(library),library_sha256=digest(library),sources_models_frozen_before_generation=True,
        demand_seed=20271101,event_seed=20271102,
        baseline_implementation='Originalv1 Client and EventController loaded from frozen source by explicit module aliases',
        contract_implementation='Originalv1 EventController; strict output-contract client only',
        neutral_implementation='Originalv1 EventController; strict neutral syntax appendix and neutral format repairs',
        plan_sha256=digest(ROOT/'docs/superpowers/plans/2026-10-04-online-llm-neutral-v3.md'),
        diagnosis_sha256=digest(ROOT/'docs/2026-10-04-online-llm-neutral-v3-diagnosis.json'))
    out.mkdir(parents=True);write(out/'freeze.json',frozen)
    sources=out/'sources';sources.mkdir()
    for rel,expected in frozen['source_sha256'].items():
        target=sources/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target);assert digest(target)==expected
    shutil.copy2(library,out/'frozen_library.json')
    try:
        used,prior=previous_inputs(out);data=generate()
        values=[(kind,index,tuple(trace[:200])) for kind in ('base','shock') for index,trace in enumerate(data[kind])]
        historical=[dict(kind=k,trace=i) for k,i,t in values if t in used]
        cross=[dict(left_kind=k,left_trace=i,right_kind=k2,right_trace=i2) for n,(k,i,t) in enumerate(values)
            for k2,i2,t2 in values[:n] if t==t2 and not (i==i2 and k!=k2)]
        if historical or cross:
            write(out/'collision_diagnosis.json',dict(inputs=data,historical_collisions=historical,cross_path_collisions=cross,
                fixed_seeds_preserved=True,no_resampling=True))
            raise RuntimeError('Fixed input collision; preserve all cases and diagnose, do not resample')
        write(out/'inputs.json',data)
        write(out/'manifest.json',dict(status='registered',phase='neutral_v3_development',development_only=True,
            methods=list(CORE.METHODS),training_seeds=[11,12],episodes=64,node_periods=38400,
            freeze_sha256=digest(out/'freeze.json'),input_sha256=digest(out/'inputs.json'),
            demand_seed=20271101,event_seed=20271102,intensities=[1.25,1.25,1.5,1.5],
            unchanged_shock_indices=[i for i,(base,shock) in enumerate(zip(data['base'],data['shock'])) if base[:200]==shock[:200]],
            prior_input_sources=prior,contracts={str(seed):CORE.contracts(out/'inputs.json',library,CORE.training(seed)) for seed in (11,12)},
            max_http_requests_batch=384,max_http_per_episode=16,max_events=4,max_semantic_requests_per_event=2,
            screening_periods=5,forecast_horizon=20,correction_periods=5,search_paths=3,review_paths=3,final_candidates=3,
            initial_generation_failure='Original three zero-rule fallback candidates; one revision only after valid initial generation',
            revision_replacement='Original candidate index0; no elite protection or execution carryover',
            selection_criterion='Development-only: mean cost below originalfeedback and mean downstream backlog not above it; all adverse pairs retained',
            real_world_deadline_guaranteed=False,no_training=True,no_random_method=True))
    except Exception as exc:
        write(out/'registration_failed.json',dict(failure=str(exc)[:1000],outputs_preserved=True));raise


def check_registered(out,library):
    manifest=read(out/'manifest.json');frozen=read(out/'freeze.json')
    assert manifest['status']=='registered' and digest(out/'freeze.json')==manifest['freeze_sha256']
    assert CORE.source_hashes()==frozen['source_sha256'] and runtime()==frozen['runtime']
    assert digest(library)==frozen['library_sha256']==digest(out/'frozen_library.json')
    assert digest(REFERENCE)==frozen['reference_input_sha256']
    for rel,expected in frozen['source_sha256'].items():
        assert digest(out/'sources'/rel)==expected
    assert digest(out/'inputs.json')==manifest['input_sha256'];CORE.validate_inputs(read(out/'inputs.json'))
    for seed in (11,12):
        assert CORE.contracts(REFERENCE,library,CORE.training(seed))==frozen['reference_model_contracts'][str(seed)]
        assert CORE.contracts(out/'inputs.json',library,CORE.training(seed))==manifest['contracts'][str(seed)]
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/online_llm_neutral/development_v3')
    parser.add_argument('--operator-library',type=Path,default=CORE.LIBRARY)
    parser.add_argument('--preflight',action='store_true',help='Freeze/register only; no HTTP or evaluation')
    opts=parser.parse_args();out=opts.output.resolve();library=opts.operator_library.resolve()
    if not os.environ.get('DEEPSEEK_API_KEY'):
        raise RuntimeError('DEEPSEEK_API_KEY missing')
    if not out.exists():
        register(out,library)
    if not (out/'manifest.json').exists() or (out/'registration_failed.json').exists():
        raise RuntimeError('Incomplete/failed registration; preserve outputs')
    if any((out/name).exists() for name in ('launch.json','failed.json','completed.json')):
        raise RuntimeError('Already launched or failed; refuse repeat')
    manifest=check_registered(out,library)
    if opts.preflight:
        print('NEUTRAL_PREFLIGHT_OK noAPI/evaluation 64episodes38400rows',str(out),flush=True);return
    with (out/'launch.json').open('x',encoding='utf-8') as stream:
        import json
        json.dump(dict(pid=os.getpid(),started=time.time(),manifest_sha256=digest(out/'manifest.json')),stream,indent=2)
    analyzer=None
    completed=[]
    try:
        analyzer=CORE.load_module('neutral_v3_analyzer_impl',Path(__file__).with_name('analyze.py'))
        for seed in (11,12):
            check_registered(out,library);label=f'seed{seed}'
            write(out/'progress.json',dict(status='evaluating',seed=seed,pid=os.getpid(),completed=completed))
            command=[sys.executable,'-u',str(Path(__file__).with_name('run.py')),'--run-name',label,
                '--input-file',str(out/'inputs.json'),'--training-directory',str(CORE.training(seed)),
                '--operator-library',str(library),'--output-root',str(out)]
            with (out/f'{label}.log').open('x',encoding='utf-8') as stream:
                result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f'{label} failed; raw requests and partial episodes preserved')
            check_registered(out,library)
            analyzer.audit_run(out/label,read(out/'inputs.json'),manifest['contracts'][str(seed)])
            completed.append(dict(seed=seed,path=str(out/label),protocol_sha256=digest(out/label/'protocol.json')))
        summary=analyzer.analyze(out,require_complete=True);check_registered(out,library)
        write(out/'completed.json',dict(status='completed',development_only=True,episodes=64,node_periods=38400,
            api_requests=summary['api_requests'],summary_sha256=digest(out/'summary.json'),all_cases_retained=True))
        write(out/'progress.json',dict(status='completed',pid=os.getpid(),completed=completed))
        print('NEUTRAL_DEVELOPMENT_COMPLETED',flush=True)
    except Exception as exc:
        write(out/'failed.json',dict(failure=str(exc)[:1000],completed=completed,outputs_preserved=True))
        try:
            if analyzer is not None:
                analyzer.analyze(out,require_complete=False)
        except Exception as error:
            write(out/'analysis_failed.json',dict(failure=str(error)[:1000]))
        raise


if __name__=='__main__':
    main()
