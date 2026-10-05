"""Read frozen, normal-validation selected inventory policies without updating them."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parameter_hash(policies):
    result=hashlib.sha256()
    for policy in policies:
        for network in (policy.actor,policy.critic):
            for name,value in network.state_dict().items():
                result.update(name.encode());result.update(value.detach().cpu().numpy().tobytes())
    return result.hexdigest()


def training(algorithm,seed):
    assert algorithm in ('happo','ippo') and seed in range(11,16)
    if algorithm=='ippo':return ROOT/f'results/ippo_learning_curve/ippo_seed{seed}_formal_v1'
    return ROOT/'results/learning_curve'/('curve_seed11_until_stable_v1' if seed==11 else f'curve_seed{seed}_formal_v1')


def load(algorithm,seed):
    directory=training(algorithm,seed)
    done=read(directory/'completed.json');audit=read(directory/'completion_audit.json')
    cfg=read(directory/'config.json')['config']
    assert cfg['seed']==[seed] and done['seed']==seed and cfg['use_centralized_V']==(algorithm=='happo')
    if algorithm=='ippo':
        assert done['actual_algorithm']=='ippo' and audit['factors_all_one'] and audit['critic_dim']==7
    assert done['best_scheduled_evaluation']['step'] in audit['model_matches']['official_best']['matching_steps']
    assert audit['evaluated_original_costs']['official_best']==done['official_best_cost']
    model_dir=Path(done['final_model_directory']).parent/'models'
    files=[directory/name for name in ('config.json','completed.json','completion_audit.json')]
    files += [model_dir/f'{label}_agent{i}.pt' for i in range(3) for label in ('actor','critic')]
    contract=dict(algorithm=algorithm,seed=seed,expected_parameter_sha256=audit['model_matches']['official_best']['sha256'],
                  expected_normal_validation_cost=done['official_best_cost'],critic_dim=21 if algorithm=='happo' else 7,
                  hashes={str(p):digest(p) for p in files},model_directory=str(model_dir))
    args=argparse.Namespace(**cfg);args.model_dir=str(model_dir)
    return args,contract
