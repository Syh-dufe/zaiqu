# Demand shock types: code-repair replay v4

## Purpose and prior attempt

This is a development-only replay of the two input batches registered in `results/online_llm_shock_types/development_v3`. The v3 driver evaluated the first seed/batch, wrote all 16 episodes and 9,600 node-period rows, then failed its final audit because a copied assertion indexed `random_screen`, a method intentionally excluded from this experiment. The evidence and raw outputs remain under the v3 result directory; that task is not counted as completed and its outcomes are excluded from v4 outcome estimates.

The v4 runner changes only that post-run assertion: it checks the actual `online_feedback` generation events and candidate/revision structure without looking for a random-comparator group. The batch driver changes only to copy and verify the already frozen v3 input hashes and to count the failed attempt against cumulative API accounting. The HAPPO policy, original online LLM prompt/parser/controller, forecast and selection process, timing, source data, shock definitions, and model weights remain unchanged. This replay reuses the exact v3 input files by SHA-256 and is therefore **previously exposed development data**, not unseen data, confirmation, or an independent test. No outcomes from v3 are used to tune the method.

## Fixed methods and cases

- Compare only frozen `happo` and original `online_feedback`; do not add random-candidate comparisons.
- Keep all five existing HAPPO training seeds 11–15 and both previously registered demand batches.
- Keep the four fixed shock types, timing profiles, 201-period base/shock traces, first-onset notification, and all normal-demand counterparts from the v3 manifest without modification.
- Re-run all ten seed/batch jobs from the beginning into a new output root. Preserve the failed v3 partial attempt as a separate provenance record.
- Make no HAPPO training updates and no prompt, parser, rule-library, or environment tuning.

## Fixed implementation and API budget

The v4 script and this protocol are frozen before registering the replay. PyTorch runs from the project venv (`torch 2.14.1+cpu`); evaluation uses CPU. The prior failed v3 attempt consumed 37 HTTP requests, including 31 semantic attempts. The v4 replay retains its registered ceiling of 1,280 HTTP and 640 semantic attempts, including at most one full-task recovery after a confirmed HTTP 402 balance restoration. Across both attempts, the cumulative hard ceiling is 1,317 HTTP and 671 semantic attempts. The planned first pass remains at most 640 HTTP and 320 semantic attempts. Credentials remain in the user environment and are never emitted in outputs.

Before running, compare copied input hashes to the v3 manifest, run ten no-API model/input contract preflights, and verify that the source, model, training metadata, library and protocol hashes remain frozen. The input collision report must explicitly label the data as replayed/exposed; it must not claim zero historical overlap or unseen paths.

## Outcomes and reporting

Complete only with 160 episodes and 96,000 node-period rows. Report paired `online_feedback - HAPPO` shock costs and downstream backlogs by shock class and training seed, plus the normal/shock difference-in-differences. Report actual applied shock magnitudes, failures, API/token use, latency, fallback behavior, and every paired improvement/tie/regression. The first v3 task's 16 episodes, 9,600 rows and 37 HTTP requests remain separately disclosed, are excluded from performance estimates, and count toward cumulative resource use.

This remains descriptive development work. Since the input paths were used in the failed attempt, results cannot establish unseen-shock generalization or serve as independent confirmation. If the implementation is valid and the policy remains promising, generate a separately registered, newly seeded confirmation set only after this replay is frozen and reviewed.
