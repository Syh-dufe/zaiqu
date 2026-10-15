# Sundial Decision-Cost Adapter Implementation Plan

> Execute serially in this worktree. Design approved by user: “开始训练吧”.

**Goal:** fit three bounded forecast parameters using closed-loop I+B cost, API0.
**Architecture:** frozen multiscale24/all_half forecasts, new location/trend/scale layer, frozen deterministic_search controller, frozen five HAPPO normal-best policies. No LLM or backbone training.
**Tech Stack:** existing CPU Python/Torch/NumPy and author environment.

## Pre-run budget correction

The design's 1530 episodes counted shock rollouts only. Every evaluated path also needs its normal control for causal-prefix audits. Total maximum is therefore 3060 episodes / 1836000 node-periods, plus a separately labeled 12-episode fixture /7200 rows. Duplicate parameter vectors are cached and reduce actual work. API cap remains0. Training up to13 vectors ×18 paths ×5 models ×2 conditions=2340; dev3 checkpoints ×9×5×2=270; holdout3 methods ×15×5×2=450. No unregistered retries.

## Locked implementation choices

- New directory only; do not edit old sources.
- Reuse ComponentController deterministic_search: original candidate construction at most27 initial scores and6 refinement scores, original independent3-path review, horizon20/five-period action/four events. Bind source SHA before new input generation.
- Data: author Merton generator, original three profile definitions; whole-background isolation across all splits. Train6, dev3, holdout5 backgrounds per type. Deterministic candidate seeds20273001..20273500; accept first noncolliding batches in split order. Offsets per split repetition are -10,-8,-6,...; no outcome filtering. Exclude all historical JSON base/shock traces, archived consumed-hash lists, and original20 validation text paths. Exclude all earlier splits. Equal base/shock within one pair allowed and disclosed.
- Parameters b/v/a per design; two sequential coordinate rounds. Compare both +/- neighbors of the coordinate's starting vector before selecting; strict training improvement only. Include initial point. All model seeds retained.
- Raw forecast cache keyed revision/report history/count/stream identity; SHA-bind every use; predictions alone reusable, never costs or inventory states across parameter settings.
- Dev chooses initial/round1/round2 by mean shock cost, ties initial then earlier. Freeze chosen parameters before first holdout run. Three retained types, no fourth-type deletion of history.
- All data development/holdout outcomes reported, no automatic retuning or paid LLM run. Gate uses overall cost vs old Sundial and Merton, existing internal service constraint, category nonjoint degradation.

## Tasks

- [x] Implement runner, independent raw-cost/forecast auditor, serial optimization driver, progress/failed/completed records.
- [x] Run original-path no-network 12-episode zero-identity fixture; check all tail audits and parameter hashes.
- [ ] Freeze sources/model/library, prepare collision-audited new inputs, register budget and gzip source package.
- [ ] Commit/push registration; verify Git stored gzip bytes and remote revision before unique launch.
- [ ] Train/dev/holdout with no API, no rerun on failure; select only by registered rules.
- [ ] Independently recompute, archive raw records, report limitations, update README and push.

## Pre-registration diagnostics retained

The initial schema check incorrectly assumed the unused201st demand must be zero; author Merton actually returns201 bounded values. Validation now preserves the original values and verifies the consumed200 periods. First12 rollouts completed, but the ambiguous audit import selected an old same-name module. Explicit file loading fixes this; all12 original rollouts were independently audited without rerunning them. A second12-episode fixture verified the final runner/metadata and zero-identity contract. Total pre-registration simulation is24 episodes/14400 rows, API0. Both attempts and diagnostics are archived; training cap3060 remains separate.
