"""Audit saved best/final checkpoints without changing model selection."""
import argparse
import csv
import hashlib
import json
import math
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    target=parser.parse_args().directory.resolve()
    if (target/'completion_audit.json').exists():raise RuntimeError('Audit already exists; preserve it')
    done=json.loads((target/'completed.json').read_text(encoding='utf-8-sig'))
    cfg=json.loads((target/'config.json').read_text(encoding='utf-8-sig'))['config']
    snapshots=json.loads((target/'snapshots.json').read_text(encoding='utf-8-sig'))
    rows=list(csv.DictReader((target/'curve.csv').open(encoding='utf-8')))
    sys.path.insert(0,str(ROOT/'experiments/learning_curve'))
    from run import stability_report
    evaluations=[float(r['mean_actor_period_cost']) for r in rows if r['phase']=='evaluation' and int(r['step'])>0]
    stable=stability_report(evaluations[:-1],done['completed_steps'])
    assert stable==done['stability']
    import torch
    torch.set_num_threads(1)
    def digest(directory):
        checksum=hashlib.sha256()
        for i in range(3):
            for label in ('actor','critic'):
                state=torch.load(directory/f'{label}_agent{i}.pt',map_location='cpu',weights_only=True)
                for name,value in state.items():checksum.update(name.encode());checksum.update(value.numpy().tobytes())
        return checksum.hexdigest()
    final_dir=Path(done['final_model_directory']);best_dir=final_dir.parent/'models'
    hashes={label:digest(directory) for label,directory in (('official_best',best_dir),('final',final_dir))}
    matches={label:dict(sha256=sha,matching_steps=[s['step'] for s in snapshots if s['parameter_sha256']==sha]) for label,sha in hashes.items()}
    assert done['best_scheduled_evaluation']['step'] in matches['official_best']['matching_steps']
    assert done['completed_steps'] in matches['final']['matching_steps'] and done['max_reload_error']==0
    sys.path.insert(0,str(ROOT/'external/liu-inventory'));os.chdir(ROOT/'external/liu-inventory')
    from envs.env_wrappers import DummyVecEnv
    from runners.separated.runner import CRunner
    measured={}
    for label,directory in (('official_best',best_dir),('final',final_dir)):
        args=argparse.Namespace(**cfg);args.model_dir=str(directory)
        envs=DummyVecEnv(args)
        runner=CRunner(dict(all_args=args,envs=envs,eval_envs=envs,num_agents=3,device=torch.device('cpu'),run_dir=target/('audit_'+label)))
        reward,_=runner.eval();measured[label]=-float(reward)
        expected=done['official_best_cost'] if label=='official_best' else done['final_eval_cost']
        assert math.isclose(measured[label],expected,abs_tol=1e-8)
        runner.writter.close();envs.close()
    record=dict(seed=done['seed'],stability_excluding_extra_final_evaluation=stable,model_matches=matches,
                evaluated_original_costs=measured,original_eval_traces=20,stop_reason=done['stop_reason'],
                note='Best selected only using original normal-demand evaluation; no disaster test data used')
    (target/'completion_audit.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print('TRAINING_AUDITED',done['seed'],done['completed_steps'],done['stop_reason'],flush=True)


if __name__=='__main__':main()
