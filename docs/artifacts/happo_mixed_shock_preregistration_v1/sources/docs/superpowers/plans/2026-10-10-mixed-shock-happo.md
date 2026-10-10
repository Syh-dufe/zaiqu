# Mixed shock HAPPO implementation plan

> Use executing-plans in the current session; preserve original frozen files.

**Goal:** Start the user-approved mixed-demand HAPPO baseline for all five seeds.
**Architecture:** Independent demand adapter and registered serial driver reuse the unchanged learning-curve observer and official PPO/HAPPO loop. Independent validation JSON replaces evaluation data in process only. Audit entry applies the same immutable validation before loading original checkpoint audit.
**Tech stack:** Existing Python3.12/Torch CPU venv, NumPy, PowerShell hidden background launch.

- [ ] Implement distribution adapter, causal local observations unchanged, full training demand ledger.
- [ ] Generate/register 100 balanced validation traces with history collision inventory, config comparison, freeze old weights and source, no training/API.
- [ ] Implement train/audit entry and failure-stopping serial driver with permanent started.lock and no overwrite.
- [ ] Inspect imports/config/registration and demand shapes without optimizer steps; do not add unit tests.
- [ ] Commit and push explicit new files and preregistration before unique launch; observe first training log/process.
- [ ] After all seeds finish, audit all outputs and archive/report separately; final new-path comparison is a subsequent stage.
