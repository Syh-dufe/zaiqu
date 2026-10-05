# Independent Shock-Type Confirmation v5

## Registration status

This protocol freezes the experiment before generating its demand traces. It is a new independent confirmation of the original real-time `online_feedback` policy against frozen HAPPO, following the descriptive v4 development replay. The v3/v4 paths and every path previously used by development or confirmation are excluded by a pre-registered, outcome-blind collision screen.

## Question and fixed methods

Does the original real-time LLM method improve total inventory-plus-backlog cost and downstream backlog over frozen HAPPO on previously unused demand trajectories under four registered demand-shock shapes?

- Methods: frozen `happo` and the original `online_feedback` implementation only. No random-candidate comparison.
- HAPPO checkpoints: the existing frozen training seeds 11–15; no training or weight updates.
- LLM: original prompt, parser, candidate generation, forecast search, screening, per-episode memory behavior, and API retry/format-repair behavior. No prompt or rule tuning.
- Environment: original three-echelon Merton-demand environment, 201-period demand traces with 200 consumed periods, unchanged costs, capacities, report interval, and observation rules.
- Outcomes: episode mean total system cost (`inventory + backlog` summed over three nodes) and episode mean downstream-node-0 backlog. Lower is better.

## Design and sample size

Generate 10 independent demand batches. Each batch contains one independently generated Merton base trace for each shock type, for 10 distinct paths per type and 40 type-specific paths in total. Cross every batch with all five frozen HAPPO seeds, both methods, and normal/shocked demand:

`10 batches × 5 models × 4 shock types × 2 methods × 2 scenarios = 800 episodes` and `480,000 node-period rows` (600 periods per episode).

Demand-generation seeds are fixed in advance to the ordered range 20271401–20271450. Use the first 10 seeds whose four base and transformed shock traces are collision-free against all historical consumed demand traces and previously accepted paths. This deterministic screen may inspect only exact path identity, never outcomes or policy results. Record every candidate seed, path hashes, rejection reason, and source manifest hash. Do not replace paths after evaluation begins. If fewer than 10 candidates qualify, stop before rollout and register a new protocol revision.

The pre-registered path timing offsets, in batch order, are `[-10,-8,-6,-4,-2,0,2,4,6,8]` periods. For offset `o`:

| Shock type | Intervals (half-open) | Factor |
|---|---|---|
| Single surge | `[80+o, 100+o)` | 1.5 |
| Sustained surge | `[70+o, 120+o)` | 1.25 |
| Double surge | `[65+o, 85+o)` and `[105+o, 125+o)` | 1.5 each |
| Surge then drop | `[80+o,100+o)` then `[100+o,140+o)` | 1.5 then 0.5 |

Surge demand uses `min(20, ceil(factor × base demand))`; drop demand uses `floor(factor × base demand)`; all other periods are unchanged. Keep zero or weak realized changes and clipping as generated; report actual post-rounding/cap magnitudes. One notification is issued at the first interval onset + 2 periods. For double surge there is no second notification. Event identity, interval, magnitude, and end time remain hidden from LLM prompts except for the registered generic emergency notification. Normal episodes receive no notification.

## Estimands and analysis

For each seed, path, and type, compute paired `online_feedback − HAPPO` differences on shocked episodes for total cost and downstream backlog. Also compute normal/shock difference-in-differences: `(LLM shock − HAPPO shock) − (LLM normal − HAPPO normal)`. Keep every seed/path pair, including ties, regressions, zero-change shocks, API errors, and fallbacks.

The two co-primary estimands are equal-weight averages across the four shock types, ten paths per type, and five HAPPO seeds: shocked episode total cost difference and shocked episode downstream backlog difference. Use 20,000 crossed bootstrap resamples with fixed analysis seed 20271003, resampling the five model seeds as one factor and resampling ten paths independently within each shock type as the second factor. Report percentile 95% two-sided intervals. Evidence for improvement on both co-primary outcomes requires each interval's upper endpoint to be below zero. The four type-specific estimates and intervals are secondary and descriptive; do not claim a per-type win based on selected paths. State the limitation of five trained checkpoints.

## API and execution limits

Run 50 serial model-seed × demand-batch jobs. Each job has four LLM shocked episodes; each episode remains capped at 16 HTTP requests and four generation events. First-pass ceilings are 3,200 HTTP requests and 1,600 semantic requests. A task that terminates on HTTP 402 may be retried once only after an availability check; the cumulative ceilings, including all failed attempts and full-task recovery, are 6,400 HTTP requests and 3,200 semantic requests. Persist all request/response metadata and token usage with recursive credential redaction. Never print, store, or commit the API credential. Stop on HTTP 401/403, a repeated 402, exceeded budget, or a non-quota program/audit error; preserve raw outputs and diagnose before any new registered attempt.

The expected first-pass planning allowance is 2,000 HTTP requests and 1,000 semantic requests, estimated from v4 throughput; it is an estimate, not a stop threshold. Report exact requests, tokens, failures, latencies, execution fallbacks, and unavailable billing information.

## Freeze and completion gates

1. Commit this protocol and the v5 source before generating demand traces.
2. Register the frozen source, protocol, original LLM library/prompt, training checkpoints, environment/upstream revision, and runtime hashes.
3. Generate the collision-screened demand inputs once and retain the complete candidate-screen audit.
4. Complete no-API preflight for all 50 input/checkpoint contracts before any rollout.
5. Run all registered jobs without editing frozen source, prompts, models, inputs, thresholds, or analysis.
6. Complete only if all 800 episodes, 480,000 node-period rows, child audits, request accounting, input/path checks, unchanged model hashes, and independent recomputation pass.
7. Preserve the raw output and report every failure, fallback, adverse pair, and actual shock magnitude. Label the result independent confirmation only if all collision and freeze checks pass. Do not use this test set to tune the method.
