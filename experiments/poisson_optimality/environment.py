"""Isolated author environment plus independent scalar transition verification."""
import json
import sys
import types
import numpy as np
from common import AUTHOR, OUT, read

def scalar_transition(inventory, backlog, pipeline, demand, actions):
    local = [int(demand), *map(int, actions[:-1])]
    requested = [local[i] + int(backlog[i]) for i in range(3)]
    available = [int(inventory[i]) + int(pipeline[i][0]) for i in range(3)]
    shipped = [min(available[i], requested[i]) for i in range(3)]
    inv = [available[i] - shipped[i] for i in range(3)]
    back = [requested[i] - shipped[i] for i in range(3)]
    arrival = [shipped[1], shipped[2], int(actions[2])]
    pipes = [list(map(int, pipeline[i][1:])) + [arrival[i]] for i in range(3)]
    reward = [-inv[i] - (back[i] if i == 0 else 0) for i in range(3)]
    return inv, back, pipes, reward

def install(lead, demand_log):
    sys.path.insert(0, str(AUTHOR))
    module = types.ModuleType('envs.poisson_frozen')
    module.__package__ = 'envs'
    module.__file__ = str(AUTHOR / 'envs/serial.py')
    exec(compile((AUTHOR / 'envs/serial.py').read_text(encoding='utf-8'), module.__file__, 'exec'), module.__dict__)
    module.LEAD_TIME = lead
    module.OBS_DIM = lead + 3
    module.H = [1, 1, 1]
    module.B = [1, 0, 0]
    module.S_I = module.S_O = 0
    validation = read(OUT / 'inputs.json')['validation']
    module.get_eval_data = lambda: (len(validation), validation)
    stream = demand_log.open('x', encoding='utf-8', newline='\n')
    def training_data():
        values = np.random.poisson(10, 200).tolist()
        stream.write(json.dumps(values) + '\n')
        stream.flush()
        return values
    module.get_training_data = training_data
    class AuditedEnv(module.Env):
        def __init__(self):
            super().__init__()
            self.checked_steps = 0
            self.raw_cost_sum = 0
            self.order_cap_hits = 0
        def state_update(self, action):
            assert len(action) == 3 and all(int(a) == a and 0 <= a <= 20 for a in action)
            expected = scalar_transition(self.inventory, self.backlog, self.order,
                                         self.demand_list[self.step_num], action)
            reward = super().state_update(action)
            actual = (self.inventory, self.backlog, self.order, reward)
            for a, b in zip(actual, expected):
                assert np.array_equal(a, b), (a, b)
            self.checked_steps += 1
            self.raw_cost_sum -= sum(reward)
            self.order_cap_hits += sum(int(a == 20) for a in action)
            return reward
        def get_processed_rewards(self, reward):
            if self.train:
                return [[0.5 * float(r) + 0.5 * float(sum(reward))] for r in reward]
            return [[float(r)] for r in reward]
    import envs.env_wrappers as wrappers
    wrappers.Env = AuditedEnv
    return wrappers, stream
