# Independent results review: case-only parser compatibility

Date: 2026-10-04. Only this new review document was written. No API, rollout, training or frozen-source changes. These are case-only parser results, distinct from neutral prompt formatting.

## Verification evidence

- Independently checked48 episodes and28,800 node-period rows. Each episode has600 unique period/node cells; I+B and both endpoint means reproduce within1e-9.
- All three paired comparisons (24 paired rows), improvement/worsening counts and adverse cases reproduce exactly. Both model hashes remain unchanged across all methods, with zero training updates. Normal and pre-notification state/action/cost records match HAPPO; all normal actual orders equal HAPPO orders.
- Registered input, child demands, source snapshots and completion-summary hashes match. All48 model/method/path/scenario records are retained.
- Independently checked 88 archive hashes and all 87 original-content hashes, including gzip decompression. 85 original files were additionally checked at their raw run paths; driver-log originals are stored under the archive mapping. The archived summary equals the raw summary.
- HTTP attempts: 132; failed attempts: 8; recorded tokens: {'prompt_tokens': 434443, 'completion_tokens': 49393, 'total_tokens': 483836, 'prompt_cache_hit_tokens': 342272, 'prompt_cache_miss_tokens': 92171}. The256 batch/16 per-shock-episode budgets hold. Runtime execution failures:0. API and screening timing sums reconstruct from raw records; child wall time totals 463.849s. Currency cost is unavailable.

## Shock-condition means

| Method | Cost per node-period | Downstream mean backlog |
|---|---:|---:|
| happo | 17.104375 | 4.719375 |
| online_feedback | 16.923750 | 4.310000 |
| case_feedback | 17.252500 | 4.516875 |

## Case-only versus unchanged feedback

Mean differences are cost +0.328750 and backlog +0.206875. Positive values mean deterioration. Cost improves/worsens in 1/7 pairs; backlog improves/worsens in 2/5 pairs. All ties and adverse cases remain in the raw summary.

| Model seed | Mean cost difference | Mean backlog difference |
|---|---:|---:|
| 11 | +0.452083 | +0.072500 |
| 12 | +0.205417 | +0.341250 |

The case-only variant does not meet the registered lower-cost/no-backlog-increase development criterion. Preserve the negative result; compatibility repair alone is not realized performance improvement.

## Independent normalization checks

- Checked 126 compilation records against raw returned candidates: 4 candidates used normalization, 4 boolean NAME tokens were changed, and 6 compilation records failed.
- Recomputed raw candidate identities, token offsets and replacement strings independently with the Python tokenizer. Every logged edit changes only a NAME true/false to True/False. Repaired strings, normalized candidate hashes and valid compiled ASTs match. The original response/candidate records are preserved.
- No new DSL variable, rule-count relaxation, prompt modification or arbitrary string normalization is implied by this compatibility mechanism.

| Method | HTTP attempts | Format failures | Generation/revision failures | API seconds | Screening seconds |
|---|---:|---:|---|---:|---:|
| online_feedback | 66 | 2 | 0/0 | 133.002 | 77.313 |
| case_feedback | 66 | 6 | 2/0 | 129.939 | 77.614 |

## Interpretation and verdict

The four paths deliberately reuse neutral-v3 development inputs as registered. They are not unseen confirmation. Both methods make fresh stochastic API draws; identical prompts do not guarantee identical candidates. Eight crossed development pairs support neither formal significance nor independent efficacy claims. No automatic adoption is justified. A selected frozen mechanism needs genuinely unseen confirmation data.

No numerical accounting defect, normalization-span mismatch or dropped adverse outcome found. Archive/content preservation checks pass. Retain all negative comparisons, failed attempts and normalization records; synchronous simulation does not establish real-world response deadlines.
