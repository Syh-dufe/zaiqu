# Matched guard-pool Merton versus response Sundial pilot

User approved starting the corrected comparison: both sides use the complete
LLM/controller mechanism; only the forecasting provider is replaced. Reuse
existing Merton guard_pool, never rerun it. Retain all previous unfavorable runs.

## Fixed scope and implementation

First same small pilot: seeds11,12; confirmation01_main.json exact consumed
demands from submission_required/v1. Four shock types, normal/shock,16 new
episodes9600 rows. Compare only this matched subset, not all-five/two-batch22.312
Merton mean. Source reference online_llm_guard_pool/development_v1/runs/
development_batch01_seed11 and seed12, group guard_pool. Pure HAPPO reference
submission_required/v1/runs/confirmation01_main_seed11 and seed12.

New forecast branch is frozen Sundial128M + multiscale24 + all_half latest-report
response + original random integer allocation. No HAPPO or Sundial training,
no prompt/DSL/parser/repair/candidate/threshold/guard/pool change. Both branches
have3+3 forecast paths, horizon20/correction5, four generation events, episode-only
memory. Existing prompt's Merton wording remains disclosed; forecast metadata
does not enter prompt. Different API dates/stochastic replies remain a limitation
of cached system comparisons; do not claim pure causal attribution/equal compute.

Unique new directory experiments/sundial_matched_guard_pool and driver
experiments/online_llm_artifacts/run_matched_guard_sundial_batch.py. The previous
original_paths batch stopped after23HTTP (20 valid,3 failed); last candidate
and its original format repair both violated the1..4-rules contract. Preserve all
raw failed/partial records and fees; do not resume or weaken parser/guard.

## Budget and verification

API cap128HTTP64 semantic,64/32 perseed; no automatic complete-task reruns.
Original one format repair stays within this cap. Stop on401/402/403, invalid
candidates after repair, hash/program/audit failure; preserve partials. Key only
Windows User; never log/save/commit. Historical costs/tokens separate.

Before launch:8 episode no-network zero-rule fixture on exact confirmation01
input; full tail auditor, frozen model, raw I+B, reports, executed DSL, response,
allocation and guard/pool reconstruction. Historical raw checksums, cost totals,
normal/pre-notice prefix, SYSTEM/model alias and parameter hash checked. Bind all
sources/inputs/models/reference raw files/fixture/prior failed scope; lossless
gzip, credential absence, Git stored bytes and push before exclusive launch.

Afterwards:paired cost tables pertype/perseed and exact equal means; full raw
audit and failure accounting; archive/report/README/commit/push. Already exposed
development, two models and one physical path pertype; no significance/general
advantage claims, no selection of favorable models or subsequent test tuning.
Reports to user cost only; internal service constraints still audited.
