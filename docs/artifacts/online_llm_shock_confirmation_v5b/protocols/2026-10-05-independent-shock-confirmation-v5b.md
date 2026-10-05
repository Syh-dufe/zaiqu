# Independent Shock-Type Confirmation v5b

## Registration status and prior preflight attempt

This protocol supersedes the failed no-rollout registration attempt recorded at `results/online_llm_shock_types/confirmation_v5`. The v5 attempt stopped before writing any input file or launching a rollout because its earliest double-surge interval violated the simulator's registered event-envelope lower bound. It made no API calls and produced no outcomes. Its first candidate demand seed, `20271401`, was sampled in memory during that failed validation and is excluded from this protocol. The original v5 source and failure record remain preserved in commit `00ccc2e` and its result directory.

This v5b protocol freezes the corrected experiment before generating any new input. It is a new independent confirmation of the original real-time `online_feedback` policy against frozen HAPPO. The v3/v4 paths, all earlier development/confirmation paths, and v5's attempted seed are excluded by a pre-registered, outcome-blind exact-collision screen.

## Question and fixed methods

Does the original real-time LLM method improve total inventory-plus-backlog cost and downstream backlog over frozen HAPPO on previously unused demand trajectories under four registered demand-shock shapes?

- Methods: frozen `happo` and original `online_feedback` only. No random-candidate comparison.
- HAPPO checkpoints: existing frozen training seeds 11–15; no training or weight updates.
- LLM: original prompt, parser, candidate generation, forecast search, screening, per-episode memory behavior, and API retry/format-repair behavior. No prompt or rule tuning.
- Environment: original three-echelon Merton-demand environment, 201-period demand traces with 200 consumed periods, unchanged costs, capacities, report interval, and observation rules.
- Outcomes: episode mean total system cost (`inventory + backlog` summed over three nodes) and episode mean downstream-node-0 backlog. Lower is better.

## Design and sample size

Generate 10 independent demand batches. Each batch contains one independently generated Merton base trace for each shock type, for 10 distinct paths per type and 40 type-specific paths in total. Cross every batch with all five frozen HAPPO seeds, both methods, and normal/shocked demand:

`10 batches × 5 models × 4 shock types × 2 methods × 2 scenarios = 800 episodes` and `480,000 node-period rows` (600 periods per episode).

Demand-generation seeds are fixed in advance to the ordered range `20271402–20271451`; seed `20271401` is explicitly excluded due to the failed preflight attempt. Use the first 10 seeds whose four base and transformed shock traces are collision-free against all historical consumed demand traces and previously accepted paths. This deterministic screen may inspect only exact path identity, never outcomes or policy results. Record every candidate seed, path hashes, rejection reason, and source manifest hash. Do not replace paths after evaluation begins. If fewer than 10 candidates qualify, stop before rollout and register a new protocol revision.

Timing offsets, in accepted-batch order, are `[-10,-8,-6,-4,-2,0,2,4,6,8]` periods. For offset `o`:

| Shock type | Intervals (half-open) | Factor |
|---|---|---|
| Single surge | `[80+o, 100+o)` | 1.5 |
| Sustained surge | `[70+o, 120+o)` | 1.25 |
| Double surge | `[75+o, 95+o)` and `[115+o, 135+o)` | 1.5 each |
| Surge then drop | `[80+o,100+o)` then `[100+o,140+o)` | 1.5 then 0.5 |

These corrected intervals keep every event envelope within the environment's supported start and duration ranges. Surge demand uses `min(20, ceil(factor × base demand))`; drop demand uses `floor(factor × base demand)`; other periods are unchanged. Keep zero or weak realized changes and clipping as generated; report actual post-rounding/cap magnitudes. One notification is issued at the first interval onset + 2 periods. For double surge there is no second notification. Event identity, interval, magnitude, and end time remain hidden from LLM prompts except for the registered generic emergency notification. Normal episodes receive no notification.

## Estimands and analysis

For each HAPPO seed, path, and type, compute paired `online_feedback − HAPPO` differences on shocked episodes for total cost and downstream backlog. Also compute normal/shock difference-in-differences: `(LLM shock − HAPPO shock) − (LLM normal − HAPPO normal)`. Keep every seed/path pair, including ties, regressions, zero-change shocks, API errors, and fallbacks.

The two co-primary estimands are equal-weight averages across four shock types, ten paths per type, and five HAPPO seeds: shocked total-cost difference and shocked downstream-backlog difference. Use 20,000 crossed bootstrap resamples with fixed analysis seed `20271003`, resampling the five model seeds as one factor and resampling ten paths independently within each shock type as the second factor. Report percentile 95% two-sided intervals. Evidence for improvement on both co-primary outcomes requires each interval's upper endpoint to be below zero. Type-specific estimates and intervals are secondary and descriptive; do not claim a per-type win based on selected paths. State the limitation of five trained checkpoints.

## API and execution limits

Run 50 serial model-seed × demand-batch jobs. Each job has four LLM shocked episodes; each episode remains capped at 16 HTTP requests and four generation events. First-pass ceilings are 3,200 HTTP requests and 1,600 semantic requests. A task that terminates on HTTP 402 may be retried once only after an availability check; cumulative ceilings including failed attempts and full-task recovery are 6,400 HTTP requests and 3,200 semantic requests. Persist request/response metadata and token usage with recursive credential redaction. Never print, store, or commit the API credential. Stop on HTTP 401/403, repeated 402, exceeded budget, or non-quota program/audit error; preserve raw outputs and diagnose before any new registered attempt.

Expected first-pass allowance is 2,000 HTTP and 1,000 semantic requests, based on v4 throughput; it is an estimate, not a stop threshold. Report exact requests, tokens, failures, latency, execution fallbacks, and unavailable billing information.

## Freeze and completion gates

1. Commit this protocol and v5b source before generating demand traces.
2. Register frozen source, protocol, original LLM library/prompt, checkpoints, environment/upstream revision, and runtime hashes.
3. Generate the collision-screened inputs once and retain the complete candidate-screen audit.
4. Complete no-API preflight for all 50 input/checkpoint contracts before rollout.
5. Run all registered jobs without editing frozen source, prompt, models, inputs, thresholds, or analysis.
6. Complete only if all 800 episodes, 480,000 node-period rows, child audits, API accounting, input checks, unchanged model hashes, and independent recomputation pass.
7. Preserve raw outputs and report every failure, fallback, adverse pair, and realized shock. Label results independent confirmation only if all collision and freeze checks pass. Never tune on these paths.
