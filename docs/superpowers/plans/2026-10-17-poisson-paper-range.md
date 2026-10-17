# Paper-range Base-stock Implementation Plan

**Goal:** Remove the extra review-period range as authorized; evaluate the fixed paper-range choice fairly.

**Architecture:** New version imports frozen baseline helpers; enumerates only r=0; writes independent raw results and audit. Existing sources and results are immutable.

**Tech Stack:** Python, NumPy, frozen inventory environment; no API.

- [ ] Freeze source/spec/plan, selection references, demand inputs and reused episode results; archive/commit registration before running.
- [ ] Recompute original-range development enumeration only and verify selection equals previously saved paper_grid_best.
- [ ] Run52 deterministic episodes, scalar/vector comparison, raw cost/IP/action and unique-node-period audit; verify hashes before/after.
- [ ] Report normal and shock comparisons with all outcomes, archive losslessly, verify Git bytes, commit/push. No new tests or unrelated training.
