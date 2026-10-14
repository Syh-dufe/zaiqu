# Sundial scenario development implementation plan

**Goal:** Evaluate the fixed adapter across 60 new synthetic paths without API or retraining.

**Architecture:** Independent driver calls the frozen forecast implementation with a separately bound output root; independent scoring retains all rows and path clusters.

**Tech Stack:** Existing CPU Python/Torch runtime, NumPy, offline Sundial checkpoint.

- [ ] Create run.py: verify old freeze and adapter SHA, register source hashes before generating paths; generate three Poisson backgrounds and old shock profiles, check historical collisions, build causal reports.
- [ ] Run frozen forecast.py with the new output binding and registered 360 cases; verify checkpoint unchanged.
- [ ] Score four methods on complete report blocks; aggregate within paths then 12 cells; bootstrap paired path clusters; independently recompute sorted-sample CRPS and MAE.
- [ ] Export all artifacts as deterministic gzip with raw/compressed SHA, scan User key absence, verify Git stored bytes; write report and push. Preserve every negative result and any failure, do not retry blindly.

Execution is inline under existing user authorization. No unit tests or new API batch; numerical experiment audits are required.
