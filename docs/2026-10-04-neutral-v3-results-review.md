# Independent results review: neutral format v3

Date: 2026-10-04. Raw-result arithmetic and accounting audit. No API, environment rollout, training or frozen-source changes. Only this new review document was written. These results concern neutral prompt formatting, not the separately authorized parser-only repair experiment.

## Verification evidence

- All64 episodes and38,400 node-period rows recompute within1e-9. Each episode has600 unique period/node cells; every cost equals I+B.
- The registered groups are happo, online_feedback, contract_feedback and neutral_feedback, crossed with both training models, all four paths and normal/shock scenarios. All six paired comparison matrices, improvement/worsening counts and adverse-pair lists reproduce exactly.
- Normal/pre-notification state, cost and orders match HAPPO across all methods. Child demands equal registered inputs; both loaded parameter hashes remain unchanged across all methods, with zero training updates.
- Registered input hash, archived source hashes and completion-summary hash match. No input or adverse case was omitted.
- Runtime execution failures: 0. HTTP attempts: 196; failed attempts: 6; first attempts: 191; repair attempts: 5; maximum per shock episode: 9. Limits384 total/16 per episode respected.
- Usage totals: {'prompt_tokens': 682997, 'completion_tokens': 68986, 'total_tokens': 751983, 'prompt_cache_hit_tokens': 365824, 'prompt_cache_miss_tokens': 317173}. API and screening times recompute from raw records; summed API time 409.834s, screening time 232.946s, child wall time 718.653s. These synchronous delays are not evidence of meeting a real-world deadline. Currency cost remains unavailable.

## Shock-condition means

| Method | Cost per node-period | Downstream mean backlog |
|---|---:|---:|
| happo | 17.104375 | 4.719375 |
| online_feedback | 17.000208 | 4.215625 |
| contract_feedback | 18.167292 | 4.915000 |
| neutral_feedback | 17.407083 | 4.219375 |

## Variants versus unchanged original feedback

| Variant | Mean cost difference | Mean backlog difference | Cost improved/worsened | Backlog improved/worsened |
|---|---:|---:|---|---|
| contract_feedback | 1.167083 | 0.699375 | 1/5 | 1/6 |
| neutral_feedback | 0.406875 | 0.003750 | 2/4 | 3/3 |

Positive differences mean deterioration. Neither strict formatting nor neutral formatting meets the registered lower-cost/no-backlog-increase development criterion versus the unchanged original feedback method. Preserve these negative findings; they do not support adopting either prompt modification.

| Training seed | Variant | Mean cost difference | Mean backlog difference |
|---|---|---:|---:|
| 11 | contract_feedback | 0.575417 | 0.513750 |
| 11 | neutral_feedback | 0.357917 | 0.236250 |
| 12 | contract_feedback | 1.758750 | 0.885000 |
| 12 | neutral_feedback | 0.455833 | -0.228750 |

## Failure and delay diagnostics

| Method | HTTP | Format failures | Transport/HTTP failures | Generation/revision failures | Best eligible option lost | API seconds | Screening seconds |
|---|---:|---:|---|---|---:|---:|---:|
| online_feedback | 67 | 5 | 0/0 | 1/0 | 0 | 132.814 | 77.443 |
| contract_feedback | 64 | 0 | 0/0 | 0/0 | 1 | 137.847 | 77.557 |
| neutral_feedback | 65 | 1 | 0/0 | 0/0 | 2 | 139.173 | 77.946 |

Format validity, synthetic candidate-loss diagnostics and changed action frequency do not prove realized performance gains. API output randomness varies by method. The eight model/path pairs are development observations, with only four demand paths and two models; no independent efficacy or formal significance claim is justified.

## Realized demand changes

| Trace | Nominal intensity | Actual window uplift | Clipped periods | Unchanged shock |
|---|---:|---:|---:|---|
| 0 | 1.25 | 32.5000% | 0 | False |
| 1 | 1.25 | 54.5455% | 0 | False |
| 2 | 1.5 | 53.9216% | 0 | False |
| 3 | 1.5 | 60.0000% | 0 | False |

All fixed traces remain included. Demand rounding/truncation, base-path heterogeneity, full-state information available to corrections and synchronous compute costs limit attribution. The old confirmation data informed development; neither it nor this v3 batch is unseen confirmation of subsequent methods.

## Verdict

No numerical accounting defect or discarded adverse outcome found. Report the strict and neutral negative comparisons and retain all raw requests/failures. The next parser-only experiment is a distinct registered development mechanism and must not be presented as a success of neutral prompt formatting.
