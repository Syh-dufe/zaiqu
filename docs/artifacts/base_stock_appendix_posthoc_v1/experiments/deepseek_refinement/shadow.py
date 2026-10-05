"""Causal branch rollouts using the unchanged author environment and actors."""
import copy
import sys
from pathlib import Path
import time
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deepseek_pilot'))
from rules import compile_rule, rule_delta, manual_delta, bounded_order


def features(env, history, orders, proposed):
    recent = float(np.mean(history[-5:])) if history else 10.
    baseline = float(np.mean(history[-25:-5])) if len(history) >= 25 else recent
    return [dict(agent=i, inventory=int(env.inventory[i]), backlog=int(env.backlog[i]),
                 pipeline=int(sum(env.order[i])), arrival=int(env.order[i][0]),
                 incoming=int(history[-1] if i == 0 and history else
                              orders[-1][i-1] if i > 0 and orders else 10),
                 recent=recent, baseline=baseline, growth=recent/max(baseline, 1e-8),
                 happo=int(proposed[i])) for i in range(3)]


def corrected(candidate, env, history, orders, proposed):
    if candidate['id'] == 'zero':
        return proposed.copy()
    fs = features(env, history, orders, proposed)
    fn = (lambda f: candidate.get('strength', 1.) * manual_delta(f)) if candidate['id'].startswith('manual') else lambda f: rule_delta(candidate['compiled'], f)
    return [bounded_order(a, fn(f)) for a, f in zip(proposed, fs)]


def snapshot(env, history):
    # Intentionally never read either real demand_list or eval_data here.
    names = ('agent_num', 'obs_dim', 'action_dim', 'step_num', 'normalize', 'level_num',
             'inventory', 'backlog', 'order', 'action_history', 'episode_max_steps', 'eval_episode_len')
    state = {k: copy.deepcopy(getattr(env, k)) for k in names}
    assert state['step_num'] == len(history)
    return state


def clone(state, history, forecast):
    from envs.serial import Env
    env = object.__new__(Env)
    for k, v in state.items():
        setattr(env, k, copy.deepcopy(v))
    env.train = False
    env.eval_index = 1  # Suppress only cross-episode bullwhip aggregation.
    env.record_act_sta = [[], [], []]
    env.demand_list = list(history) + list(forecast)
    assert not hasattr(env, 'eval_data')
    return env


def forecasts(history, trace, period, method='residual', report_age=0):
    rng = np.random.default_rng(20261013 + 1000*trace + period)
    horizon = min(20, 200-period)
    if method=='merton':
        # Public generator transition, conditioned approximately on last observed integer.
        # No latent state, future real demands, event multiplier or ending time is read.
        # Propagate across the unreported interval without reading actual demands.
        latent=np.full(6,np.log((history[-1] if history else 10.)+.5));values=np.zeros((6,horizon+report_age),dtype=int)
        for t in range(horizon+report_age):
            z=rng.normal(0,1,6);n=rng.poisson(15,6);z2=rng.normal(0,2,6)
            latent+=np.sqrt(15)*.01*z+.01*np.sqrt(n)*z2
            values[:,t]=np.clip(np.floor(np.exp(np.clip(latent,-20,20))),0,20).astype(int)
        values = values[:, report_age:]
    else:
        assert method=='residual'
        mean = np.mean(history[-5:]) if history else 10.
        residual = np.array(history[-20:] if history else [10.], dtype=float)
        residual -= residual.mean()
        values = np.clip(np.rint(mean+rng.choice(residual, size=(6, horizon))), 0, 20).astype(int)
    return values[:3].tolist(), values[3:].tolist()


@torch.no_grad()
def score(candidate, state, history, orders, proposed, recurrent, actors, paths, correction_periods=20, reports=None):
    costs = []; downstream = []; node_backlog = []
    try:
        for path in paths:
            # In report mode the prefix is padding for absolute demand indexing only.
            # Never place withheld real history in a branch available to the selector.
            prefix = history if reports is None else [0] * state['step_num']
            env = clone(state, prefix, path)
            branch_reports = reports.projection() if reports is not None else None
            hist = history.copy() if branch_reports is None else branch_reports.delivered_history.copy()
            acts = copy.deepcopy(orders)
            rnn = [r.copy() for r in recurrent]
            base = proposed.copy(); cost = 0.; backlog = np.zeros(3)
            for t, demand in enumerate(path):
                active = candidate if t < correction_periods else {'id':'zero'}
                actual = corrected(active, env, hist, acts, base)
                obs, reward, _, _ = env.step(actual, one_hot=False)
                cost -= float(np.sum(reward)); backlog += env.backlog
                if branch_reports is None:
                    hist.append(int(demand))
                else:
                    branch_reports.observe(demand, env.step_num)
                    hist = branch_reports.delivered_history.copy()
                acts.append(actual)
                if t+1 < len(path):
                    base = []
                    for i, act in enumerate(actors):
                        a, next_rnn = act(np.asarray(obs[i])[None], rnn[i],
                                          np.ones((1, 1), dtype=np.float32), None, deterministic=True)
                        base.append(int(a.detach().cpu().numpy().reshape(-1)[0]))
                        rnn[i] = next_rnn.detach().cpu().numpy().copy()
            costs.append(cost); downstream.append(float(backlog[0])); node_backlog.append(backlog.tolist())
        return {'id': candidate['id'], 'cost': float(np.mean(costs)),
                'downstream': float(np.mean(downstream)),
                'node_backlog': np.mean(node_backlog, axis=0).tolist(), 'valid': True}
    except Exception as exc:
        return {'id': candidate['id'], 'valid': False, 'failure': type(exc).__name__}


def eligible(candidate_score, zero_score):
    return (candidate_score['valid'] and candidate_score['cost'] <= .99*zero_score['cost']
            and candidate_score['downstream'] <= zero_score['downstream'])


def select(candidates, state, history, orders, proposed, recurrent, actors, paths, correction_periods=20, reports=None, review=True):
    start = time.perf_counter()
    search = [score(c, state, history, orders, proposed, recurrent, actors, paths[0], correction_periods, reports) for c in candidates]
    zero = search[0]; assert zero['id'] == 'zero' and zero['valid']
    accepted = [s for s in search[1:] if eligible(s, zero)]
    chosen = min(accepted, key=lambda s: s['cost'])['id'] if accepted else 'zero'
    chosen_rule = next(c for c in candidates if c['id'] == chosen)
    if not review:
        return chosen, {'search':search,'validation_zero':None,'validation_candidate':None,'chosen':chosen,
                        'seconds':time.perf_counter()-start,'review':False}
    validation_zero = score(candidates[0], state, history, orders, proposed, recurrent, actors, paths[1], correction_periods, reports)
    validation = score(chosen_rule, state, history, orders, proposed, recurrent, actors, paths[1], correction_periods, reports)
    if chosen != 'zero' and not eligible(validation, validation_zero):
        chosen = 'zero'
    return chosen, {'search': search, 'validation_zero': validation_zero,
                    'validation_candidate': validation, 'chosen': chosen,
                    'seconds': time.perf_counter()-start}
