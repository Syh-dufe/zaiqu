"""Preregistered constant random candidates; no fitting to test performance."""
import random


def random_rules():
    rng=random.Random(20261230)
    return [dict(explanation='Fixed random constant-vector diagnostic, seed20261230',
                 rules=[dict(when=f'agent == {i}',delta=str(rng.randint(-2,2))) for i in range(3)]) for _ in range(3)]
