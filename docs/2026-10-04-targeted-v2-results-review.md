# Independent results review: targeted online LLM v2

Date: 2026-10-04. Independent arithmetic and record checks; no API, rollout, training or frozen-source edit. Only this review document was written.

## Verification evidence

- All64 episodes and38,400 node-period rows checked independently. Every episode has600 unique period/node records; I+B and both reported episode means reproduce within1e-9.
- The full2-model x4-path x4-method x2-scenario keys are retained. Normal and pre-notification cost/state/order records match HAPPO. All six comparison matrices and all adverse-pair records reproduce exactly.
- Both model parameter hashes remain unchanged across all four methods, with zero training updates. Input/child-demand equality, registered input hash, archived source hashes and completion-summary hash match.
- Runtime execution fallbacks: 0. Actual wall time summed across both model runs: 711.216s.
- HTTP attempts: 197; failed attempts: 5; format failures: 5; first attempts: 192; repair attempts: 5; maximum per shock episode: 10. Registered ceilings384 per batch/16 per episode respected.
- Token usage independently sums to {'prompt_tokens': 693998, 'completion_tokens': 64629, 'total_tokens': 758627, 'prompt_cache_hit_tokens': 414976, 'prompt_cache_miss_tokens': 279022}. Monetary cost is unavailable and is not inferred.

## Full shock-condition means

| Method | Cost per node-period | Downstream mean backlog |
|---|---:|---:|
| happo | 26.827083 | 36.009375 |
| online_feedback | 24.758542 | 31.256250 |
| contract_feedback | 25.308333 | 33.061875 |
| elite_feedback | 25.143125 | 32.079375 |

## Targeted variants versus unchanged online feedback

| Variant | Mean cost difference | Mean backlog difference | Cost improved/worsened | Backlog improved/worsened |
|---|---:|---:|---|---|
| contract_feedback | 0.549792 | 1.805625 | 3/5 | 2/6 |
| elite_feedback | 0.384583 | 0.823125 | 2/6 | 3/5 |

Positive differences mean deterioration. Neither targeted variant meets the preregistered development criterion of lower mean cost with no increase in mean backlog versus unchanged online feedback. These negative findings must remain visible; this batch does not justify adopting either modification.

| Training seed | Variant | Mean cost difference | Mean backlog difference |
|---|---|---:|---:|
| 11 | contract_feedback | 0.891667 | 3.902500 |
| 11 | elite_feedback | 0.333333 | 2.337500 |
| 12 | contract_feedback | 0.207917 | -0.291250 |
| 12 | elite_feedback | 0.435833 | -0.691250 |

## Implementation diagnostics

| Method | HTTP attempts | Format failures | Generation failures | Revision failures | Best eligible search option lost |
|---|---:|---:|---:|---:|---:|
| online_feedback | 69 | 5 | 0 | 0 | 0 |
| contract_feedback | 64 | 0 | 0 | 0 | 0 |
| elite_feedback | 64 | 0 | 0 | 0 | 0 |

- 13 elite retention events reproduce from successful physical executions with changed orders. Selection alone is not counted as an executed carryover.
- The original feedback had five format failures, all repaired; both targeted variants had none. Every method had zero lost-best-eligible search events in this batch, so it provides no observed baseline loss event against which to measure the benefit of protection.
- Formatting and candidate-protection diagnostics concern the mechanism and synthetic search predictions. Improvement in either diagnostic cannot substitute for lower realized inventory cost/backlog.
- API output stochasticity differs across methods; eight paired development cases do not prove the format/retention change caused the observed mean differences. No formal significance or independent efficacy claim is supported.

## Realized shock conditions

| Trace | Nominal intensity | Realized demand-window uplift | Clipped periods | Unchanged demand path |
|---|---:|---:|---:|---|
| 0 | 1.25 | 28.9308% | 0 | False |
| 1 | 1.25 | 17.5481% | 10 | False |
| 2 | 1.5 | 43.6667% | 13 | False |
| 3 | 1.5 | 52.3121% | 1 | False |

Demand rounding/clipping and baseline demand heterogeneity remain part of the fixed distribution. Any later change needs a separately registered development version; a final frozen mechanism needs new unseen confirmation paths. The old confirmation data already informed this design and cannot establish the new variants independently.

## Verdict

No numerical accounting defect or dropped adverse case found. Preserve and report the negative comparison against unchanged feedback; retain raw requests, failed attempts and search/execution diagnostics. No targeted modification is eligible under the registered adoption criterion.
