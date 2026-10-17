# Poisson baseline comparison execution plan

**Goal:** Evaluate ten frozen Poisson HAPPO best policies against a development-calibrated stationary Base-stock on twenty new common test paths, API0.

**Architecture:** Independent comparison directory imports the immutable Poisson adapter, evaluates all constant targets in two predeclared quantile grids, freezes selected targets, then generates and evaluates holdout. Author policy weights never update. Raw episodes support a separate file-based audit.

**Tech stack:** Existing CPU PyTorch, NumPy, standard library Poisson CDF recurrence/JSON/CSV/gzip/SHA/subprocess. Preparation found SciPy absent before any registration or evaluation; its failed-import source and diagnostic are preserved. No package installation or training-source change is needed.

1. Implement separate sources under experiments/poisson_baseline_comparison; reuse the existing Poisson code without edits. Define stationary stock position and supplier outstanding ledger explicitly.
2. Preflight independent scalar and author state transition, target-grid construction, action capping, both actor dimensions and both critics. Reproduce all original best validation costs during formal run before holdout.
3. Register source, spec, plan, twenty reserved development paths, all training completion/config/best metadata and60 actual best weight files. Bind source and weight hashes. Archive original bytes, verify User key absence and Git stored bytes; push before run.
4. Run all candidate development scores, freeze selections, then generate twenty holdout trajectories with within/history uniqueness checks. Preserve full scan and both grid origins.
5. Evaluate all ten HAPPO and both selected Base-stock policies, persist full period and episode records, source/model SHA before/after.
6. Recompute costs independently from period files, verify unique identities, all240 holdout/200 validation episodes, parameters, inventory position and ledgers. Run descriptive crossed bootstrap and report every model/path.
7. Archive training and evaluation originals with gzip/SHA, update report and README, verify Git blobs then commit/push. All negative/unstable seeds remain. Prepare a separate frozen implementation for full-mechanism shock comparison next.

Routine execution is authorized by the user; do not ask again to run this accepted comparison. Do not weaken the reference, rerun old paid batches, or alter the frozen training protocol.
