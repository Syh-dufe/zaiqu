"""Sequential, fixed-input formal evaluation; no training or API calls."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from inputs import validate_batch

ROOT=Path(__file__).resolve().parents[2]


def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-directory',type=Path)
    parser.add_argument('--development-input',type=Path)
    parser.add_argument('--training-directory',type=Path,default=ROOT/'results/learning_curve/curve_seed11_until_stable_v1')
    parser.add_argument('--methods',nargs='+',default=['happo','llm_library'],choices=['happo','llm_library','llm_no_screen','llm_search_only','random_screen'])
    parser.add_argument('--stage',choices=['a','b','c'],default='a')
    parser.add_argument('--report-interval',type=int,default=3,choices=[1,3,5])
    parser.add_argument('--run-name',required=True)
    args=parser.parse_args()
    if bool(args.input_directory)==bool(args.development_input):parser.error('Choose formal directory or existing development input')
    if not args.run_name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.run_name):parser.error('Invalid run name')
    if args.methods[0]!='happo' or len(set(args.methods))!=len(args.methods):parser.error('Require unique methods with HAPPO first')
    files=[]
    if args.input_directory:
        directory=args.input_directory.resolve();manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8-sig'))
        protocol=directory/'protocol_snapshot.md'
        if not protocol.exists():protocol=ROOT/'docs/2026-10-03-formal-experiment-protocol.md'
        if digest(protocol)!=manifest['protocol_sha256']:raise RuntimeError('Protocol changed after inputs generated')
        for record in manifest['batches']:
            file=directory/record['file']
            if digest(file)!=record['sha256']:raise RuntimeError('Input hash differs')
            validate_batch(json.loads(file.read_text(encoding='utf-8-sig')),4);files.append(file)
        if len(files)!=5:raise RuntimeError('Require all five formal batches')
    else:
        file=args.development_input.resolve();data=json.loads(file.read_text(encoding='utf-8-sig'))
        validate_batch(data,len(data['base']));files=[file]
    out=ROOT/'results/formal_evaluation'/args.run_name
    if out.exists():parser.error('Refuse overwrite')
    training=args.training_directory.resolve();audit=json.loads((training/'completion_audit.json').read_text(encoding='utf-8-sig'))
    sources=[Path(__file__),Path(__file__).with_name('inputs.py'),Path(__file__).with_name('prepare.py'),Path(__file__).with_name('analyze.py'),Path(__file__).with_name('ablations.py'),
             ROOT/'experiments/deepseek_refinement/run.py',ROOT/'experiments/deepseek_refinement/shadow.py',
             ROOT/'experiments/deepseek_refinement/reports.py',ROOT/'experiments/deepseek_pilot/rules.py']
    library=ROOT/'docs/artifacts/operator_discovery_v1/repaired_library.json'
    out.mkdir(parents=True)
    dependencies={name:importlib.metadata.version(name) for name in ('numpy','torch','matplotlib')}
    training_config=json.loads((training/'config.json').read_text(encoding='utf-8-sig'))['config']
    run_manifest=dict(mode='development_flow_check' if args.development_input else 'formal_stage_'+args.stage,
        training_seed=training_config['seed'][0],
        project_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in sources},
        library_sha256=digest(library),training_directory=str(training),model_parameter_sha256=audit['model_matches']['official_best']['sha256'],
        python=sys.version,platform=platform.platform(),dependencies=dependencies,
        inputs=[dict(path=str(p),sha256=digest(p)) for p in files],methods=args.methods,report_interval=args.report_interval,
        protocol_sha256=digest(protocol if args.input_directory else ROOT/'docs/2026-10-03-formal-experiment-protocol.md'))
    write(out/'manifest.json',run_manifest);started=time.perf_counter();results=[]
    for i,file in enumerate(files,1):
        data=json.loads(file.read_text(encoding='utf-8-sig'));batch=f'{args.run_name}_batch{i}'
        command=[sys.executable,'-u',str(ROOT/'experiments/deepseek_refinement/run.py'),
                 '--run-name',batch,'--output-root',str(out),'--input-file',str(file),
                 '--training-directory',str(training),'--methods',*args.methods,'--cases',str(len(data['base'])),
                 '--operator-library',str(library),'--correction-periods','5','--predictor','merton',
                 '--report-interval',str(args.report_interval)]
        write(out/'progress.json',dict(status='running',active_batch=batch,completed=results,commands=command))
        with (out/f'{batch}.log').open('w',encoding='utf-8') as log:
            completed=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if completed.returncode:
            write(out/'progress.json',dict(status='failed',active_batch=batch,exit_code=completed.returncode,completed=results))
            raise RuntimeError(f'Batch failed; preserved log: {batch}')
        completion=json.loads((out/batch/'completed.json').read_text(encoding='utf-8-sig'))
        if completion['calls'] or completion['training_updates'] or completion['runtime_failures']:raise RuntimeError('Formal frozen evaluation audit failed')
        if any(not check['unchanged'] or check['before']!=run_manifest['model_parameter_sha256'] for check in completion['parameter_checks'].values()):raise RuntimeError('Model mismatch')
        if any(digest(ROOT/name)!=value for name,value in run_manifest['source_sha256'].items()) or digest(library)!=run_manifest['library_sha256']:raise RuntimeError('Source changed during evaluation')
        results.append(dict(name=batch,episodes=completion['episodes'],rows=completion['rows'],wall_seconds=completion['wall_seconds']))
        print('BATCH_COMPLETED',i,len(files),completion['episodes'],flush=True)
    write(out/'progress.json',dict(status='completed',completed=results,wall_seconds=time.perf_counter()-started))
    print('STAGE_COMPLETED',out,flush=True)


if __name__=='__main__':main()
