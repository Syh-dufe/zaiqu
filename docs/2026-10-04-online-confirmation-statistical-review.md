# Independent statistical review: online confirmation v1

Date: 2026-10-04. Scope: read-only recomputation from the completed raw confirmation records. No API calls, environment rollouts, controller changes or performance tuning. Only this review document was written.

## Accounting and reproducibility

- Independently checked all 1000 episodes and 600,000 node-period rows. Each episode has 600 unique period/node cells; inventory plus backlog reproduces every recorded cost. Both episode endpoints reproduce within 1e-9.
- The five models and twenty trajectories form the registered crossed design. All seven paired comparison matrices, counts and adverse-pair records reproduce exactly.
- All seven 20,000-draw crossed 95% bootstrap intervals reproduce exactly; the primary 97.5% intervals and evidence criterion reproduce exactly. Sampling used independent model and trajectory indices with seed 20261221.
- Every child demand record equals its registered input. Registered input hashes, archived core/wrapper source hashes and final summary hash match; all five method parameter checks for every model/batch report unchanged loaded parameters and zero training updates.
- Runtime fallback records: 0. HTTP attempts: 1069; first attempts: 989; repair attempts: 80; failed attempts: 91. Maximum requests in an episode: 11, below the registered limit of 16; batch limit is 2,000.
- Usage totals reproduce exactly: {'prompt_tokens': 3442824, 'completion_tokens': 403606, 'total_tokens': 3846430, 'prompt_cache_hit_tokens': 2030976, 'prompt_cache_miss_tokens': 1411848}. Failed attempts are retained; no currency cost is inferred from token counts.

## Primary endpoint results

| Endpoint | HAPPO mean | Online feedback mean | Difference: feedback minus HAPPO | 97.5% interval | Percent reduction |
|---|---:|---:|---:|---|---:|
| Cost per node-period | 20.646117 | 19.897100 | -0.749017 | [-1.434949, -0.237748] | 3.6279% |
| Downstream mean backlog | 18.877100 | 17.699550 | -1.177550 | [-2.712888, -0.225350] | 6.2380% |

Both primary mean differences and both 97.5% upper bounds are below zero. The registered stronger-evidence criterion is met for this fixed test distribution and method. This is an average-effect statement, not a claim of universal trajectory improvement.

| Endpoint | Improved | Tied | Worsened |
|---|---:|---:|---:|
| cost | 66 | 8 | 26 |
| backlog | 65 | 14 | 21 |

Of 100 primary pairs, 34 worsen at least one endpoint; all remain in the summary. The five per-model primary mean differences are:

| Training seed | Cost difference | Backlog difference |
|---|---:|---:|
| 11 | -0.904500 | -1.591750 |
| 12 | -0.631500 | -1.013500 |
| 13 | -0.550500 | -0.787000 |
| 14 | -0.593667 | -1.353250 |
| 15 | -1.064917 | -1.142250 |

## Secondary contrasts

| Reference for online feedback | Cost difference | Descriptive 95% interval | Backlog difference | Descriptive 95% interval |
|---|---:|---|---:|---|
| llm_library | -0.593917 | [-1.229801, -0.003798] | -1.072600 | [-2.348456, -0.168945] |
| online_once | -0.496050 | [-1.153157, 0.022357] | -0.364850 | [-1.417515, 0.578211] |
| random_screen | 0.400483 | [-0.223779, 1.039235] | 0.247900 | [-0.707304, 1.221005] |

Online feedback has higher pooled means than matched random screening on both endpoints: cost +0.400483 and backlog +0.247900. Both descriptive intervals cross zero. There is no support here for claiming superiority to the matched random diagnostic or attributing the primary improvement specifically to LLM rule content.

Secondary intervals are descriptive and have no correction across the full comparison family. They do not independently establish an LLM-specific contribution. The random comparator matches event/candidate/scoring opportunities and extra information, but is a constant-vector diagnostic rather than a tuned competitive inventory baseline.

## Actual demand uplift strata

| Actual uplift stratum | Trajectories | Model/trajectory pairs | Primary cost difference | Primary backlog difference |
|---|---:|---:|---:|---:|
| zero | 0 | 0 | Not estimable | Not estimable |
| positive_below10percent | 1 | 5 | -2.826000 | -7.310000 |
| at_least10percent | 19 | 95 | -0.639702 | -0.854789 |

Strata use demand-window uplift after rounding and clipping, not the nominal multiplier. They are preregistered descriptive breakdowns, with all trajectories retained. This confirmation contains no zero-uplift trajectory, so that stratum is not estimable. Under the registered controller, a zero-uplift path would still receive the emergency notification; improvement on such a path would reflect notification-triggered correction without an actual demand increase. The single below-10% trajectory accounts for approximately 18.87% of the aggregate cost reduction and 31.04% of the backlog reduction. The remaining nineteen trajectories with at least 10% realized uplift also have negative mean differences on both endpoints, so the confirmation benefit is not confined to that low-uplift trajectory. Low-uplift paths can nevertheless expose baseline inventory-policy weaknesses. Overall primary improvement therefore does not establish disaster-specific adaptation.

Five training models give limited information about variation across future training runs. Forecast/random draws repeat for corresponding local trace indices across batches as registered; inference pertains to the fixed mechanism and its specified randomization. The synchronous API simulation also does not demonstrate real-world execution deadlines.

## Review conclusion

The numerical summary and registered primary statistical decision reproduce from raw data. No numerical accounting defect or dropped adverse case was found. Report the primary average improvement together with the adverse-pair counts, secondary comparison caveats and actual-uplift strata.
