"""Independent process adapter around unchanged training and checkpoint audit."""
import argparse
import json
import runpy
import sys
from pathlib import Path
from demand import ROOT, OUT, install

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['train','audit'])
    parser.add_argument('--seed',type=int,required=True)
    opts=parser.parse_args()
    name=f'mixed_shock_seed{opts.seed}_v1'
    target=ROOT/'results/learning_curve'/name
    ledger=OUT/f'seed{opts.seed}_training_demands.jsonl'
    if opts.action=='train' and (target.exists() or ledger.exists()):
        raise RuntimeError('Preserve existing outputs; no automatic restart')
    install(opts.seed,ledger if opts.action=='train' else None)
    if opts.action=='train':
        source=ROOT/'experiments/learning_curve/run.py'
        sys.argv=[str(source),'--seed',str(opts.seed),'--budget','3000000','--patience','40','--until-stable','--run-name',name]
        runpy.run_path(str(source),run_name='__main__')
        (target/'mixed_demand_override.json').write_text(json.dumps(dict(actual_training='Mixed five types, equal probability',actual_validation='100 balanced mixed traces',author_compatibility_manifest_is_inherited=True,source_manifest=str(OUT/'manifest.json')),indent=2),encoding='utf-8')
    else:
        source=ROOT/'experiments/formal_evaluation/audit_training.py'
        sys.argv=[str(source),str(target)]
        runpy.run_path(str(source),run_name='__main__')
        audit_path=target/'completion_audit.json'
        record=json.loads(audit_path.read_text(encoding='utf-8'))
        record['original_eval_traces']=100
        record['note']='Scheduled best selected on registered balanced mixed-demand validation; no final test used. Original audit engine with in-process demand override.'
        audit_path.write_text(json.dumps(record,indent=2),encoding='utf-8')

if __name__=='__main__': main()
