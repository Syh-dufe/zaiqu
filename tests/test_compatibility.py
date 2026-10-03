import argparse
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("compatibility", ROOT / "experiments/emergency_compatibility/train.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def official_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=list(range(10)))
    parser.add_argument("--num_env_steps", type=int, default=3000000)
    return parser


class SeedCompatibility(unittest.TestCase):
    def test_defaults_unchanged(self):
        parser = launcher.seed_list_parser(official_parser)
        self.assertEqual(vars(parser.parse_args([])), vars(official_parser().parse_args([])))

    def test_single_seed_is_iterable(self):
        args = launcher.seed_list_parser(official_parser).parse_args(["--seed", "11"])
        self.assertEqual(args.seed, [11])

    def test_multiple_seeds_and_budget(self):
        args = launcher.seed_list_parser(official_parser).parse_args(["--seed", "11", "23", "--num_env_steps", "5000"])
        self.assertEqual(args.seed, [11, 23])
        self.assertEqual(args.num_env_steps, 5000)


if __name__ == "__main__":
    unittest.main()
