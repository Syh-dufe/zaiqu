# Online Guard and Pool Implementation Plan

> **For agentic workers:** Use executing-plans inline; do not spawn agents or modify any prior frozen object.

**Goal:** Implement auditable same-state revision protection and pool review, then validate separately from the running confirmation.

**Architecture:** Pure decision functions plus an isolated copy of the original controller namespace. The original full strategy uses its unmodified class. New controller variants retain the original client and causal inputs.

**Tech Stack:** Python, original prediction scorer, frozen HAPPO, DeepSeek original client.

- [x] Create `experiments/online_llm_guard_pool/policy.py`: `keep_revision(original, revised, zero)` and `select_pool(candidates, scorer, review)`; reject invalid/nonfinite inputs, preserve strict replacement and original eligibility thresholds.
- [x] Create `controller.py`: load original controller globals into an independent namespace; asserted replacements add three variant names, guarded replacement audit, and pool selector for both generation and rescreen. Never assign to original controller module globals.
- [x] Create `check.py`: fake deterministic scorer verifies veto-best/pass-second, all-veto fallback, invalid replacement, equal/worse replacement, service regression, and old eligible candidate protection. Run `python experiments/online_llm_guard_pool/check.py`; observed `GUARD_POOL_CHECK_PASSED` with no API. `check_controller.py` additionally passed generation/rescreen/reset checks with mocked state, not real environment.
- [ ] Build an independent real runner and no-network deployment fixture on exposed inputs, check original SYSTEM/Client identity, source and all model hashes, costs, notification/report causal indexes, original normal/pre-notice actions, candidate pool size and extra scores.
- [ ] After current batch completion and lossless archival, register frozen development source/input/model contracts and complete unique driver. Run 400 development episodes with original+happo+three variants, first HTTP2560/semantic1280; audit all240000 rows and all attempts before evaluating the fixed gate.
- [ ] If gate passes, register400 internal-validation episodes on batch03/08 with same fixed budget; otherwise complete negative report. Do not start a paid batch before unique launch/freeze/preflight are registered.
- [ ] After both pass, preregister the new confirmation before unseen input generation. Report extra forecasts, API reliability and all negative seeds. Publish code/reports with credential absence and Git byte checks.

The design fixes exact scenario split, seed inclusion, thresholds and budget. No schedule tuning, prompt changes, parser changes or random candidate comparison in this version.
