"""Validate the original 201-value sequences before consuming 200 periods."""
import math


def validate_batch(data, cases):
    if any(len(data.get(k, [])) != cases for k in ('base', 'shock', 'events')):
        raise ValueError('Input case count differs')
    for base, shock, event in zip(data['base'], data['shock'], data['events']):
        if len(base) != 201 or len(shock) != 201:
            raise ValueError('Expected full original 201-value sequences')
        if any(type(v) is not int or not 0 <= v <= 20 for v in base + shock):
            raise ValueError('Demand must be integer in original bounds')
        start, duration = event['start_index'], event['duration']
        if type(start) is not int or type(duration) is not int or not 60 <= start <= 100 or not 20 <= duration <= 40:
            raise ValueError('Event differs from registered distribution')
        expected = [min(20, math.ceil(1.5*v)) if start <= i < start+duration else v for i, v in enumerate(base)]
        if shock != expected: raise ValueError('Shock differs from registered transformation')
    return data
