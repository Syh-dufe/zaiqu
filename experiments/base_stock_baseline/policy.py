"""Causal local-history base-stock adaptation; not an official Liu implementation."""
from collections import deque
import math
import numpy as np


class BaseStock:
    def __init__(self, z=8, information='local', rounding='ceil', initial_history=None):
        if information not in ('local', 'report_mean') or rounding not in ('ceil', 'floor'):
            raise ValueError('Unknown policy variant')
        self.z = z
        self.information = information
        self.rounding = rounding
        initial = [10.0]*40 if initial_history is None else list(initial_history)
        if len(initial) != 40:
            raise ValueError('Initial history must contain 40 observations')
        self.history = [deque(initial, maxlen=40) for _ in range(3)]
        self.pending = [[] for _ in range(3)]
        self.unshipped = [0.0]*3

    def decide(self, inventory, backlog, pipeline):
        decisions = []
        for i in range(3):
            mean = float(np.mean(self.history[i]))
            variance = float(np.var(self.history[i], ddof=0))
            target = 4*mean + self.z*math.sqrt(4*variance)
            position = float(inventory[i] + sum(pipeline[i]) + self.unshipped[i] - backlog[i])
            integer = math.ceil(target-position) if self.rounding == 'ceil' else math.floor(target-position)
            decisions.append(dict(mean=mean, variance=variance, target=target, position=position,
                                  unshipped=self.unshipped[i], action=max(0, min(20, integer))))
        return decisions

    def observe(self, local_demands, orders, newly_shipped):
        # Completed-period information only. Each new shipment transfers unshipped
        # orders into the physical pipeline, so the two accounts do not overlap.
        for i in range(3):
            value = self.unshipped[i] + orders[i] - newly_shipped[i]
            if value < -1e-8:
                raise ValueError('Shipment exceeds outstanding orders')
            self.unshipped[i] = max(0.0, value)
            if self.information == 'local':
                self.history[i].append(float(local_demands[i]))
            else:
                self.pending[i].append(float(local_demands[i]))
                if len(self.pending[i]) == 3:
                    mean = sum(self.pending[i])/3
                    self.history[i].extend([mean]*3)
                    self.pending[i].clear()
