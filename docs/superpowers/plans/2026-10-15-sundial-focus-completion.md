# Sundial focused seed completion implementation plan

**Goal:** Finish seeds13..15 on only double-surge and surge-then-drop, reusing audited11/12.

**Architecture:** Independent subset evaluator and scope-adjusted immutable raw audit; fixed-input replay preflight demonstrates identical behavior before paid serial tasks.

**Tech Stack:** Existing CPU Python/Torch, frozen HAPPO/Sundial24-param output adapter, registered DeepSeek client.

- [ ] runner.py: compile isolated original evaluator with asserted2-trace changes, preserve source indices2/3 and environment wrap, add scoped contract/source hashes.
- [ ] audit.py: exact identities2methods×2scenarios×2traces×200×3, all old cost/action/causality/forecast/guard/model checks retained, raw float32 declared.
- [ ] preflight.py: offline replay old seed11 valid candidates and attempts, full8 episodes, exact actions/states/cost/selected paths against immutable old rows, no network.
- [ ] batch.py: freeze old sources/weights/all reusable raw bytes, register192/96 first caps384/192 cumulative, publish/push, permanent unique lock and serial seeds13..15 with one402 recovery.
- [ ] analyze.py: reuse11/12+new13..15, all40 episodes/10shock pairs, per-type/seed/normal/DID and negative counts, no independent demand inference; archive raw partials/fees.
- [ ] Independent summary recomputation, gzip/SHA/key absence/Git stored byte checks, README/results commit push. Keep old user-stopped batch stopped.

Inline execution under explicit user authorization. Numerical experiment contracts required, no new unit-test suite or parameter tuning.
