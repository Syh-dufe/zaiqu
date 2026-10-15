"""Use the exact frozen six-rule raw auditor for each additional model seed."""
def audit(runner,*a,**kw):
    frozen=runner.module('unchanged_six_rule_extension_auditor',runner.ROOT/'experiments/sundial_six_rules/audit.py')
    result=frozen.audit(runner,*a,**kw)
    assert result['rule_limit']==6 and result['historical_merton_rule_limit']==4
    return result
