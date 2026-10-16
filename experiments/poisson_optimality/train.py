"""Train one registered Poisson HAPPO model without editing author files."""
import argparse
import csv
import hashlib
import random
import sys
import time
import traceback
from pathlib import Path
from common import AUTHOR, OUT, sha, verify, write

def parameter_sha(policies):
    h = hashlib.sha256()
    for policy in policies:
        for label in ('actor', 'critic'):
            for name, value in getattr(policy, label).state_dict().items():
                h.update(name.encode())
                h.update(value.detach().cpu().numpy().tobytes())
    return h.hexdigest()

def execute(options):
    verify()
    target = OUT / ('fixtures' if options.fixture else 'runs') / f'L{options.lead}_seed{options.seed}'
    target.mkdir(parents=True, exist_ok=False)
    started = time.time()
    try:
        import numpy as np
        import torch
        from environment import install
        wrappers, demand_stream = install(options.lead, target / 'training_demands.jsonl')
        from config import get_config
        from runners.separated.runner import CRunner
        args = get_config().parse_args([])
        args.seed = [options.seed]
        args.num_env_steps = options.budget
        args.experiment_name = f'poisson10_L{options.lead}_seed{options.seed}'
        args.scenario_name = 'Poisson10_SpecialCost'
        args.cuda = False
        random.seed(options.seed)
        np.random.seed(options.seed)
        torch.manual_seed(options.seed)
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        envs, eval_envs = wrappers.SubprocVecEnv(args), wrappers.DummyVecEnv(args)
        rows = []
        class Observed(CRunner):
            def __init__(self, config):
                super().__init__(config)
                self.steps = 0
                self.raw_previous = 0
                self.eval_phase = 'scheduled'
                self.best = None
                self.agent_updates = [0, 0, 0]
                for i, trainer in enumerate(self.trainer):
                    original = trainer.train
                    def counted(buffer, _i=i, _original=original):
                        self.agent_updates[_i] += 1
                        return _original(buffer)
                    trainer.train = counted
            def record(self, phase, cost):
                assert np.isfinite(cost)
                rows.append({'step': self.steps, 'phase': phase, 'mean_echelon_period_cost': float(cost)})
                with (target / 'curve.csv').open('w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                write(target / 'progress.json', {'step': self.steps, 'last': rows[-1],
                      'elapsed_seconds': time.time() - started, 'agent_updates': self.agent_updates})
            def train(self):
                raw_now = sum(e.raw_cost_sum for e in self.envs.env_list)
                cost = (raw_now - self.raw_previous) / 3000
                mixed = -float(np.mean([np.mean(b.rewards) for b in self.buffer])) / 2
                assert np.isclose(cost, mixed, rtol=1e-6, atol=1e-4), (cost, mixed)
                self.raw_previous = raw_now
                result = super().train()
                self.steps += 1000
                assert self.agent_updates == [self.steps // 1000] * 3
                self.record('training', cost)
                if self.steps % 100000 == 0:
                    self.checkpoint(target / 'snapshots' / f'step{self.steps}')
                return result
            def eval(self):
                raw_env = self.eval_envs.env_list[0]
                before, count = raw_env.raw_cost_sum, raw_env.checked_steps
                result = super().eval()
                assert raw_env.checked_steps - count == 4000
                cost = (raw_env.raw_cost_sum - before) / 12000
                assert np.isclose(cost, -float(result[0]), atol=1e-9)
                self.record(self.eval_phase, cost)
                return result
            def save(self):
                super().save()
                self.best = {'step': self.steps, 'validation_cost': rows[-1]['mean_echelon_period_cost'],
                             'parameter_sha256': parameter_sha(self.policy)}
                write(target / 'best.json', self.best)
            def checkpoint(self, directory):
                directory.mkdir(parents=True, exist_ok=False)
                previous = self.save_dir
                self.save_dir = str(directory)
                CRunner.save(self)
                self.save_dir = previous
                write(directory / 'parameters.json', {'parameter_sha256': parameter_sha(self.policy),
                      'step': self.steps, 'files': {p.name: sha(p) for p in directory.glob('*.pt')}})
            def reload(self, directory):
                for i, policy in enumerate(self.policy):
                    for label in ('actor', 'critic'):
                        getattr(policy, label).load_state_dict(torch.load(
                            directory / f'{label}_agent{i}.pt', map_location='cpu', weights_only=True))
        runner = Observed({'all_args': args, 'envs': envs, 'eval_envs': eval_envs,
                           'num_agents': 3, 'device': torch.device('cpu'), 'run_dir': target})
        write(target / 'config.json', {'arguments': vars(args), 'lambda': 10,
              'lead_time': options.lead, 'inventory': 0, 'pipeline': 0, 'backlog': 0,
              'holding': [1, 1, 1], 'backlog_cost': [1, 0, 0], 'reward': '0.5*local+0.5*sum',
              'actor_dimension': options.lead + 3, 'critic_dimension': 3 * (options.lead + 3),
              'input_sha256': sha(OUT / 'inputs.json'), 'python': sys.version,
              'torch': torch.__version__, 'numpy': np.__version__, 'api_calls': 0})
        result = runner.run()
        stop_reason = 'original_no_improvement' if result is not None else 'budget'
        runner.checkpoint(target / 'final_models')
        final_sha = parameter_sha(runner.policy)
        runner.eval_phase = 'terminal_excluded_from_selection'
        final_cost = -float(runner.eval()[0])
        audits = []
        for label, directory, expected_sha, expected_cost in [
            ('final', target / 'final_models', final_sha, final_cost),
            *([] if runner.best is None else [('best', target / 'models', runner.best['parameter_sha256'], runner.best['validation_cost'])])]:
            runner.reload(directory)
            assert parameter_sha(runner.policy) == expected_sha
            runner.eval_phase = f'reload_{label}'
            actual_cost = -float(runner.eval()[0])
            assert np.isclose(actual_cost, expected_cost, rtol=0, atol=1e-9)
            audits.append({'checkpoint': label, 'parameter_sha256': expected_sha,
                           'expected_cost': expected_cost, 'reloaded_cost': actual_cost,
                           'files': {p.name: sha(p) for p in directory.glob('*.pt')}})
        assert sum(e.checked_steps for e in envs.env_list) == runner.steps
        demand_stream.close()
        runner.writter.close()
        verify()
        summary = {'seed': options.seed, 'lead_time': options.lead, 'lambda': 10,
                   'fixture': options.fixture, 'completed_steps': runner.steps, 'budget': options.budget,
                   'stop_reason': stop_reason, 'best': runner.best, 'final_cost': final_cost,
                   'wall_seconds': time.time() - started, 'api_calls': 0,
                   'agent_updates': runner.agent_updates, 'audited_training_steps': runner.steps,
                   'audited_evaluation_steps': eval_envs.env_list[0].checked_steps,
                   'training_demand_sha256': sha(target / 'training_demands.jsonl'),
                   'training_order_cap_hits': sum(e.order_cap_hits for e in envs.env_list),
                   'reload_audits': audits, 'claim': 'adapted reproduction; no optimality proof'}
        write(target / 'completed.json', summary)
        print('COMPLETED', summary, flush=True)
    except BaseException:
        write(target / 'failed.json', {'traceback': traceback.format_exc(), 'wall_seconds': time.time() - started})
        raise

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--lead', type=int, choices=[2, 4], required=True)
    p.add_argument('--seed', type=int, choices=range(11, 16), required=True)
    p.add_argument('--budget', type=int, default=3000000)
    p.add_argument('--fixture', action='store_true')
    opts = p.parse_args()
    assert opts.budget > 0 and opts.budget % 1000 == 0
    if not opts.fixture:
        assert opts.budget == 3000000
    execute(opts)
