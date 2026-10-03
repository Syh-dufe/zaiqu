"""Checks for fixed, auditable formal input consumption."""
import copy
import unittest
from inputs import validate_batch


class FixedInputs(unittest.TestCase):
    def setUp(self):
        self.data = {'base': [[10]*201]*2,
                     'events': [{'start_index': 60, 'duration': 20}]*2}
        self.data['shock'] = [[15 if 60 <= i < 80 else 10 for i in range(201)] for _ in range(2)]

    def test_valid(self):
        self.assertEqual(validate_batch(self.data, 2), self.data)

    def test_future_changes_rejected(self):
        changed = copy.deepcopy(self.data)
        changed['shock'][0][85] = 12
        with self.assertRaises(ValueError): validate_batch(changed, 2)

    def test_wrong_length_rejected(self):
        changed = copy.deepcopy(self.data)
        changed['base'][0] = changed['base'][0][:200]
        with self.assertRaises(ValueError): validate_batch(changed, 2)

    def test_bad_event_rejected(self):
        changed = copy.deepcopy(self.data)
        changed['events'][0] = {'start_index': 10, 'duration': 20}
        with self.assertRaises(ValueError): validate_batch(changed, 2)


if __name__ == '__main__': unittest.main()
