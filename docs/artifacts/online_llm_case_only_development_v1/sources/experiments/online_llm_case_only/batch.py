"""Freeze before copying fixed neutral v3 development inputs; exclusive serial development run."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
if 'case_only_run_core' in sys.modules:
    CORE=sys.modules['case_only_run_core']
    if Path(CORE.__file__).resolve()!=Path(__file__).with_name('run.py').resolve():
        raise RuntimeError('Case-only run alias collision')
else:
    spec=importlib.util.spec_from_file_location('case_only_run_core',Path(__file__).with_name('run.py'))
    CORE=importlib.util.module_from_spec(spec);sys.modules[spec.name]=CORE;spec.loader.exec_module(CORE)
read,write,digest=CORE.read,CORE.write,CORE.digest
REFERENCE=CORE.REFERENCE
REFERENCE_MANIFEST=CORE.REFERENCE_MANIFEST


def runtime():
    import numpy as np
    import torch
    return dict(python_executable=sys.executable,python_version=sys.version,
        python_sha256=digest(Path(sys.executable)),numpy_version=np.__version__,torch_version=torch.__version__)


def register(out,library):
    assert not out.exists()
    frozen=dict(phase='case_only_development',source_sha256=CORE.source_hashes(),runtime=runtime(),
        reference_input_path=str(REFERENCE),reference_input_sha256=digest(REFERENCE),
        reference_model_contracts={str(seed):CORE.contracts(REFERENCE,library,CORE.training(seed)) for seed in (11,12)},
        library_path=str(library),library_sha256=digest(library),sources_models_frozen_before_input_copy=True,
        reference_manifest_path=str(REFERENCE_MANIFEST),reference_manifest_sha256=digest(REFERENCE_MANIFEST),
        reference_input_sha256_matches_neutral_v3_manifest=read(REFERENCE_MANIFEST)['input_sha256']==digest(REFERENCE),
        demand_seed=20271101,event_seed=20271102,
        baseline_implementation='Originalv1 Client and EventController loaded from frozen source by explicit module aliases',
        case_implementation='Originalv1 Client loaded separately; only compile_rule reference replaces lowercase boolean NAME tokens',
        same_original_system_and_generate_body=True,reused_inputs_are_development_only=True,
        plan_sha256=digest(ROOT/'docs/superpowers/plans/2026-10-04-online-llm-bool-case-only.md'))
    out.mkdir(parents=True);write(out/'freeze.json',frozen)
    sources=out/'sources';sources.mkdir()
    for rel,expected in frozen['source_sha256'].items():
        target=sources/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,target);assert digest(target)==expected
    shutil.copy2(library,out/'frozen_library.json')
    try:
        assert digest(REFERENCE)==read(REFERENCE_MANIFEST)['input_sha256'], 'Neutral v3 reference input hash mismatch'
        data=CORE.validate_inputs(read(REFERENCE))
        shutil.copy2(REFERENCE,out/'inputs.json')
        assert digest(out/'inputs.json')==digest(REFERENCE)
        write(out/'manifest.json',dict(status='registered',phase='case_only_development',development_only=True,
            methods=list(CORE.METHODS),training_seeds=[11,12],episodes=48,node_periods=28800,
            freeze_sha256=digest(out/'freeze.json'),input_sha256=digest(out/'inputs.json'),
            demand_seed=20271101,event_seed=20271102,intensities=[1.25,1.25,1.5,1.5],
            unchanged_shock_indices=[i for i,(base,shock) in enumerate(zip(data['base'],data['shock'])) if base[:200]==shock[:200]],
            reference_input_reused=True,no_new_test_claim=True,no_collision_resampling=True,contracts={str(seed):CORE.contracts(out/'inputs.json',library,CORE.training(seed)) for seed in (11,12)},
            max_http_requests_batch=256,max_http_per_episode=16,max_events=4,max_semantic_requests_per_event=2,
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
    assert digest(REFERENCE)==frozen['reference_input_sha256']==read(REFERENCE_MANIFEST)['input_sha256']
    assert digest(REFERENCE_MANIFEST)==frozen['reference_manifest_sha256']
    for rel,expected in frozen['source_sha256'].items():
        assert digest(out/'sources'/rel)==expected
    assert digest(out/'inputs.json')==manifest['input_sha256'];CORE.validate_inputs(read(out/'inputs.json'))
    for seed in (11,12):
        assert CORE.contracts(REFERENCE,library,CORE.training(seed))==frozen['reference_model_contracts'][str(seed)]
        assert CORE.contracts(out/'inputs.json',library,CORE.training(seed))==manifest['contracts'][str(seed)]
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'results/online_llm_case_only/development_v1')
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
        print('CASE_ONLY_PREFLIGHT_OK noAPI/evaluation 48episodes28800rows',str(out),flush=True);return
    with (out/'launch.json').open('x',encoding='utf-8') as stream:
        import json
        json.dump(dict(pid=os.getpid(),started=time.time(),manifest_sha256=digest(out/'manifest.json')),stream,indent=2)
    analyzer=None
    completed=[]
    try:
        analyzer=CORE.load_module('case_only_analyzer_impl',Path(__file__).with_name('analyze.py'))
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
        write(out/'completed.json',dict(status='completed',development_only=True,episodes=48,node_periods=28800,
            api_requests=summary['api_requests'],summary_sha256=digest(out/'summary.json'),all_cases_retained=True))
        write(out/'progress.json',dict(status='completed',pid=os.getpid(),completed=completed))
        print('CASE_ONLY_DEVELOPMENT_COMPLETED',flush=True)
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
