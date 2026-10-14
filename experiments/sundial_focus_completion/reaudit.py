"""Reuse unchanged offline simulation, explicitly repair source-introspection scope."""
import csv,shutil
from pathlib import Path
import runner
core=runner.core;ROOT=runner.ROOT;SOURCE=ROOT/'results/sundial_focus_completion/no_api_replay_v1';OUT=ROOT/'results/sundial_focus_completion/no_api_reaudit_v2'
REFERENCE=ROOT/'results/sundial_closed_loop_development/development_v2/runs/batch01_seed11'
assert not OUT.exists() and (SOURCE/'completed.json').exists() and (SOURCE/'failed.json').exists()
OUT.mkdir(parents=True);bindings={}
for p in SOURCE.rglob('*'):
 if not p.is_file():continue
 dest=OUT/p.relative_to(SOURCE);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);assert core.digest(p)==core.digest(dest);bindings[str(p)]=core.digest(p)
if (OUT/'audit.json').exists():(OUT/'audit.json').rename(OUT/'original_partial_audit.json')
data=core.read(OUT/'demands.json');contract=core.read(OUT/'protocol.json');auditor=runner.module('focus_repaired_scope_auditor',runner.HERE/'audit.py')
result=auditor.audit(runner,OUT,data,contract['expected_parameter_sha256'],True)
with (REFERENCE/'periods.csv').open(encoding='utf-8',newline='') as f:old={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])):r for r in csv.DictReader(f)}
with (OUT/'periods.csv').open(encoding='utf-8',newline='') as f:
 for r in csv.DictReader(f):
  k=(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node']));assert all(r[n]==old[k][n] for n in ('demand','actual_order','policy_order','inventory','backlog','cost','chosen'))
old_scores={(r['group'],r['trace'],r['decision_period']):r for r in core.read(REFERENCE/'scores.json')}
for r in core.read(OUT/'scores.json'):
 old=old_scores[r['group'],r['trace'],r['decision_period']];assert r['forecasts']==old['forecasts'] and r['chosen']==old['chosen']
assert len(core.read(OUT/'calls.json'))==len([r for r in core.read(REFERENCE/'calls.json') if r['group'] in runner.METHODS and r['trace'] in runner.SELECTED])
core.write(OUT/'preflight_passed.json',dict(**result,network_requests=0,old_response_replay=True,exact_old_node_periods=True,exact_old_forecast_choices=True,simulation_reused=True,not_new_performance_evidence=True,source_bindings=bindings))
print('FOCUS_EXACT_REPLAY_REAUDIT_PASSED',flush=True)
