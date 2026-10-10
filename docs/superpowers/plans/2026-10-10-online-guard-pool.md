# Online Guard and Pool Implementation Plan

> **For agentic workers:** Use executing-plans inline; do not spawn agents or modify any prior frozen object.

**Goal:** Implement auditable same-state revision protection and pool review, then validate separately from the running confirmation.

**Architecture:** Pure decision functions plus an isolated copy of the original controller namespace. The original full strategy uses its unmodified class. New controller variants retain the original client and causal inputs.

**Tech Stack:** Python, original prediction scorer, frozen HAPPO, DeepSeek original client.

- [x] Create `experiments/online_llm_guard_pool/policy.py`: `keep_revision(original, revised, zero)` and `select_pool(candidates, scorer, review)`; reject invalid/nonfinite inputs, preserve strict replacement and original eligibility thresholds.
- [x] Create `controller.py`: load original controller globals into an independent namespace; asserted replacements add three variant names, guarded replacement audit, and pool selector for both generation and rescreen. Never assign to original controller module globals.
- [x] Create `check.py`: fake deterministic scorer verifies veto-best/pass-second, all-veto fallback, invalid replacement, equal/worse replacement, service regression, and old eligible candidate protection. Run `python experiments/online_llm_guard_pool/check.py`; observed `GUARD_POOL_CHECK_PASSED` with no API. `check_controller.py` additionally passed generation/rescreen/reset checks with mocked state, not real environment.
- [x] Build an independent real runner and no-network deployment fixture on exposed inputs. `offline_fixture_v2` passed 40 episodes/24000 unique node-periods, original prompt/client/controller identity, frozen seed11 deployment and same-input HAPPO replay, causal indexes, all raw costs, 32 revision decisions and 95 pool reviews. This is synthetic-reply interface evidence, not actual API performance. The reboot-interrupted v1 is retained separately; explicit auditor loading corrects a bare-import collision.
- [ ] Per the user's explicit cache-reuse request, register only three new variants after auditing/binding ten completed controls on identical inputs/models. Run 240 new episodes/144000 rows, reuse160 control episodes/96000 rows, first HTTP1920/semantic960. Audit all new raw rows and cached hashes before the same fixed gate. No repeated baseline API and no need to wait for unrelated sensitivity completion.
- [ ] If gate passes, register400 internal-validation episodes on batch03/08 with same fixed budget; otherwise complete negative report. Do not start a paid batch before unique launch/freeze/preflight are registered.
- [ ] After both pass, preregister the new confirmation before unseen input generation. Report extra forecasts, API reliability and all negative seeds. Publish code/reports with credential absence and Git byte checks.

The design fixes exact scenario split, seed inclusion, thresholds and budget. No schedule tuning, prompt changes, parser changes or random candidate comparison in this version.

The independent paid driver is `experiments/online_llm_guard_pool_driver/batch.py`. Registration now requires independently audited, hash-bound completed control tasks, not whole-package completion. Registration, ten no-API task contracts, variant-only cached-reference fixture, publication package and exact Git blobs must be pushed before its unique paid launch. The intended combined comparison remains400 episodes/240000 rows, only240 newly run. Original readiness v2 remains archived; `offline_fixture_v3_cached` checks variant-only deployment plus exact cached HAPPO normal/pre-notice actions. Current paid development has NOT started.
