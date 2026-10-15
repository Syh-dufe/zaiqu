"""Seed-only extension of the frozen six-rule response Sundial engine."""
import argparse,importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('frozen_six_rule_engine',ROOT/'experiments/sundial_six_rules/runner.py')
six=importlib.util.module_from_spec(spec);sys.modules[spec.name]=six;spec.loader.exec_module(six)
core,guard,original,predictor,paths=six.core,six.guard,six.original,six.predictor,six.paths
module=six.module;METHODS=six.METHODS;OLD_SYSTEM=six.OLD_SYSTEM
old_sources=core.source_hashes
def sources():
    value=old_sources();files=list(HERE.glob('*.py'))+[ROOT/'docs/superpowers/plans/2026-10-15-sundial-six-rules-extension.md']
    value.update({str(p.relative_to(ROOT)):core.digest(p) for p in files});return value
core.source_hashes=sources
old_contracts=core.contracts
def contracts(*a,**kw):
    value=old_contracts(*a,**kw);value.update(api_budget_total=192,extension_seeds=[13,14,15],unchanged_six_rule_engine=True);return value
core.contracts=contracts
configure=six.configure
if __name__=='__main__':
    p=argparse.ArgumentParser(add_help=False);p.add_argument('--seed',type=int,choices=(13,14,15),required=True);a,rest=p.parse_known_args();configure(a.seed);sys.argv=[sys.argv[0]]+rest;core.main()
