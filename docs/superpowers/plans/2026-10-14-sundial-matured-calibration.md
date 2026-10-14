# Sundial matured-report calibration implementation plan

**Goal:** Test one fixed causal bias adjustment for sustained demand shifts, with API0 and no old batch restart.

**Architecture:** A standalone state module accepts only delivered report history and prior predictions. A separate scorer owns future labels; a sequential driver performs cached replay then frozen-new-input validation.

**Tech Stack:** Existing CPU Torch/Sundial runtime, NumPy, immutable model/adapter and historical sources.

- [ ] calibration.py: register first fully future block, mature only when reports arrive, unique block labels, last3/recent6 window, fixed half-median bounded shift, path reset.
- [ ] run.py: verify old freezes and stopped batch hashes; cache-only A on all four types and both completed seeds; independently bound before-generation new protocol/source/model SHA.
- [ ] Generate B12 collision-free paths in fixed seed order; causal k3 reconstruction, 15 forecasts per path, original predictor/raw samples and common allocation seeds, model SHA before/after.
- [ ] score.py: same6 deployment paths, raw per-window scoring values, path aggregation, all references/types and preset gate; no inventory cost claim.
- [ ] verify.py: reconstruct every matured error from causal reports, unique label/window/state resets, demand transforms/hash/collisions, independent scalar CRPS/MAE, adapter/model/source hashes.
- [ ] Preserve all diagnostics/negative paths, deterministic gzip and SHA/key absence, Git exact stored bytes; report README commit push. Do not run paid closed-loop or resume stopped batch.

Inline execution under user adjustment authorization; experimental numerical audits only, no unit-test suite or hyperparameter scan.
