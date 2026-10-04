# Unseen demand shock types: preregistered development batch v2

This fixed protocol is hashed in `results/online_llm_shock_types/development_v2/freeze.json` before the new Merton paths are generated. The first registration attempt (`development_v1`) stopped before generating paths or running an episode; its diagnostic is retained separately.

## Question and scope

Does the original online LLM feedback policy retain its paired advantage over frozen HAPPO when demand disturbances have shapes not used in the earlier impulse confirmation? This is a **development experiment**, not an independent test and not a claim of real-disaster validation.

The LLM prompt, case-sensitive parser, rule DSL, candidate generation and repair behavior, feedback controller, forecast/scoring procedure, notification timing, report cadence, inventory transition, and HAPPO weights remain those of the original online method. No policy is trained or tuned. Only HAPPO and `online_feedback` run; no random-candidate or other LLM variant is included.

## Frozen model and inputs

- Evaluate all five frozen HAPPO models from training seeds 11–15, including seeds that did not meet the separate empirical-stability criterion.
- Use the author's Merton generator `merton(200, 20)` and two fixed NumPy demand seeds: 20271101 and 20271102. Each seed generates four sequential, distinct 201-period base traces, one assigned to each shock type.
- The four shock profiles appear once in each batch, in this fixed order:
  1. `single_surge`: one 20-period 1.5× surge.
  2. `sustained_surge`: one 50-period 1.25× surge.
  3. `double_surge`: two separated 20-period 1.5× surges.
  4. `surge_then_drop`: a 20-period 1.5× surge immediately followed by a 40-period 0.5× demand drop.
- Batch 1 intervals (zero-based, end-exclusive): `[80,100)`, `[70,120)`, `[65,85)` and `[105,125)`, `[80,100)` and `[100,140)` respectively.
- Batch 2 intervals: `[90,110)`, `[80,130)`, `[70,90)` and `[110,130)`, `[90,110)` and `[110,150)` respectively.
- Upward changes use `min(20, ceil(factor × base demand))`; the downward segment uses `floor(0.5 × base demand)`. All other periods equal the paired base trace. Keep and report paths whose integer rounding or cap makes part or all of a shock ineffective.
- The simulator gives one emergency notification at the first interval's onset, using the existing fixed two-period delay. It does not disclose the shock type, start/end, or magnitude to the LLM. A double surge has no second notification; the unchanged periodic re-scoring behavior remains in force.
- Before evaluation, compare each consumed base and shocked demand sequence against prior JSON records under `results/` and `docs/artifacts/`. If any collision or duplicate is found, preserve the registration failure and inputs; do not silently replace or drop paths.

The method/source/library/model contracts are frozen before generating new inputs. The frozen SHA-256 manifest includes the dedicated runner and batch driver, unchanged original online method sources and dependencies, operator library, all five model artifacts, and their training metadata.

## Size and budget

Five model seeds × two batches × four shock profiles × two methods × two scenarios (normal and shocked) = **160 episodes and 96,000 node-period rows**. This gives 40 paired shock cases overall and 10 paired cases per shock class. Each paired shock case also has a normal-demand counterpart. Each LLM episode retains its existing 16-HTTP ceiling; the batch ceiling is 640 HTTP attempts and 320 semantic requests. API failures and fallbacks count against the budget and remain in the output.

Runs are serial. A missing credential, HTTP 401/402/403, or exhausted account balance stops the batch while preserving all output. A failed attempt is never overwritten. Resume work, if needed, uses a new attempt directory after diagnosing the failure; completed seed/batch jobs are skipped.

## Outcomes and analysis

For each paired shock case, report mean three-node `I+B` cost over 200 periods and downstream node-0 mean backlog over 200 periods. The primary development contrast is `online_feedback − HAPPO` on the shocked episode. Also report the difference-in-differences `(LLM shock − LLM normal) − (HAPPO shock − HAPPO normal)` to separate general normal-demand correction from shock response. Summarize both by shock type and training seed, with all paired values and counts of improvement, tie, and regression.

Report actual demand changes within each registered interval, cap and rounding, notification and action timing, API calls/tokens/failures, execution fallbacks, and wall time. Independently verify all 600 period-node rows per episode, `cost = inventory + backlog`, paired inputs, identical HAPPO parameters before and after, normal/pre-notification action identity, and all registered episode/API counts.

This small development batch is descriptive. Do not make inferential or generalization claims from its 10 paths per type. Do not tune the method on its registered paths and call them a test. If the frozen original method remains promising across the four types, freeze the method and create new, independently generated paths for a later confirmation; otherwise report the negative result and diagnose it without hiding cases.
