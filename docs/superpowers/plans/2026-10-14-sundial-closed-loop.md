# Sundial closed-loop development implementation plan

**Goal:** Deploy the frozen adapter and compare actual costs across four systems on identical exposed development inputs.

**Architecture:** Independent runner/controller/predictor/auditor and serial driver; reuse old immutable HAPPO/LLM components through isolated namespaces. No old source edits.

**Tech Stack:** Existing CPU Torch runtime, offline Sundial128M, registered DeepSeek deployment.

- [ ] predictor.py: frozen model loader, per-episode sampled block cache, fixed 24-parameter transform, seeded integer total/capacity-constrained period allocation, before/after model hash.
- [ ] controller.py/runner.py: inject four forecast sources at generation and re-screen, retain original prompt and guard_pool; record raw samples, stream identities, all deployed paths and prediction audit.
- [ ] prepare.py: bind old scenario inputs and adapter hashes; select suffix1 by index for all three backgrounds; append nonconsumed sentinel0; fixed15 tasks and API caps.
- [ ] preflight.py/audit.py: networking-forbidden full32 episode fixture; independent node-period cost/report/DSL/guard checks, seeded allocation reconstruction, matched normal/pre-notice behavior; verify raw Sundial inference against recorded output on causal fixture case; execute same tail as real driver.
- [ ] batch.py/analyze.py: unique started lock, pushed-registration check, preserve all attempts, one402 recovery/task, cost-only public report, explicit development gate and all model/path/background breakdowns.
- [ ] publish registration with source/model/input/fixture hashes, gzip SHA and credential scan, check Git stored bytes, commit/push; launch hidden unique driver, record process IDs. Final independent summary audit and complete archive/report push when finished.

Inline execution under the approved scope. Numerical contract and experiment audits required; no unit-test suite added.
