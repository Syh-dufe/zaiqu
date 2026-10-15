# Response stageA horizon audit recovery

Original cfafcef/cc9190d froze experiment correctly, but independent auditor
expected forecast_audit.horizon which the original deterministic wrapper never
writes. Both zero-response simulations completed8episodes4800rows each, no API,
before auditor KeyError('horizon') stopped original driver. Original failed.json
and stale progress are preserved; no original source, inputs or model changed.

New independent auditor reconstructs h=min(20,201-decision_period), exactly the
registered forecast horizon min(20,200-env.step_num). Validate all six stored
path lengths against h before running the original audit with ONLY that missing
field lookup replaced. No exception suppression, eligibility or cost changes.
Reaudit both complete outputs without simulation/API, bind every original byte,
then reuse both tasks. Remaining8 tasks use exact original runner/input/options,
max2 CPU processes, no overwrite or paid calls. New driver and status root
results/sundial_change_response_recovery/v1; simulation outputs stay original
results/sundial_change_response/v1/runs. Original failed root is not restarted.

New recovery freeze covers old registration dependencies, repaired audit source,
protocol and all reused raw files. Exclusive lock, verify before/after tasks,
preserve any failure, stop dispatch, allow already-started task to finish. Same
five-candidate selection, zero baseline and >=1% cost gate, no validation yet.
All costs, failures and recovery must be archived transparently; no claim that
initial independent audit passed or that old simulations had no compute expense.
