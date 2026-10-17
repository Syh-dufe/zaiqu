# Poisson HAPPO training and stationary Base-stock results

## Scope and interpretation
User specified Poisson mean10, five seeds11..15 at lead2/4. Three echelons,200 periods, empty initial inventory/pipeline, holding[1,1,1],backlog coefficients[1,0,0],actions0..20. Training reward is paper local+total mixture(alpha0.5), not public code local+mean. Network and sequential update reuse author code. These explicit adaptations and unidentified original special-test mean prevent an exact numerical replication claim. No API was used.

## Training completed
Ten models finished,945000total environment steps,2.5199hours summed job wall time. All stopped at original patience10, not budget3m. Early stopping is not convergence; no seeds discarded. Best means actually saved scheduled-validation model; final separately retained. Every training transition was checked during the run. Later read-only audit verified all4725recorded training demand trajectories, curve/update counts, source SHA, checkpoint file SHA and best/final reload costs. Floating summation differences were at most7.11e-15, within the original1e-9cost audit tolerance; an initial extra exact-equality check was diagnosed, with no frozen training code or audit changes.

|Seed|L2 steps|L2 best validation|L2 final validation|L4 steps|L4 best validation|L4 final validation|
|---|---:|---:|---:|---:|---:|---:|
|11|85000|28.093917|111.959750|60000|40.274917|273.270750|
|12|120000|9.050167|100.646833|90000|19.807750|126.416833|
|13|115000|8.812083|8.985917|95000|38.166833|92.949667|
|14|110000|10.733667|17.396750|135000|10.455250|12.094333|
|15|65000|22.278917|35.381667|70000|60.581750|64.907417|

The mean best validation costs15.79375/33.85730 are model-selection measurements. Strong late training degradation appears in several seeds. This run does not reproduce the paper's approximately15%optimality gap. Hypotheses about reward implementation, stopping and reference definition need separate controlled diagnostics; do not weaken the baseline or select favorable seeds.

## Independently held-out Base-stock comparison
Fixed-target stationary policy, not old H40/z. Predeclared finite candidate grids combined paper-inspired quantile bounds and an explicit one-review-period allowance; all candidates evaluated on20reserved development paths, choices frozen before20new holdout paths generated. Registered candidates150forL2 and228forL4. Selected installation targets[34,29,25]/[55,49,44] came from review-allowance1. Thus the strongest reported reference includes our timing adaptation and is not exactly the paper's numeric baseline, nor a certified global optimum.

|Seed|L2 HAPPO holdout|L4 HAPPO holdout|
|---|---:|---:|
|11|24.821000|38.898083|
|12|9.929167|19.344000|
|13|9.377000|35.077333|
|14|10.372417|10.590833|
|15|18.494833|57.080333|
|Mean|14.598883|32.198117|
|Stationary Base-stock|3.283333|5.760500|

HAPPO minus Base-stock=11.31555/26.43762, relative+344.64%/+458.95%. Descriptive crossed-bootstrap95%cost-difference intervals[6.35454,17.29313]/[12.48420,40.83332],20000replicates seed20275004, model and path axes resampled. All100seed/path pairs perL have higher HAPPO cost. No claim of near-optimality, HAPPO superiority or LLM performance follows.

200original-validation episodes exactly reproduce model selection costs;240holdout episodes include200learned-policy episodes and40deterministic reference episodes. Do not count five copies of the same deterministic policy as five training seeds. Total440episodes264000node-periods. Separate file audit recomputed transitions, stock positions, supplier outstanding ledgers, identities, physical demand and realized weighted cost. SHA/selection checks passed. API0. Simulation108.73seconds, excluding later audit/archive work.

## Artifacts and next stage
- Training root: results/poisson_optimality/formal_v1; original registration2ff393c.
- Training originals: docs/artifacts/poisson_optimality_completed, lossless gzip originals including intermediate snapshots and fixture files, per-file manifest; these are this small Poisson experiment's weights, not all project/IPPO weights.
- Comparison root: results/poisson_baseline_comparison/v1; registration3264c4e.
- Comparison originals: docs/artifacts/poisson_baseline_comparison_completed; includes all scans, inputs, raw periods and audit, with no overwritten results.
- Preparation SciPy import failure happened before any simulation/registration and its source/diagnostic is preserved in comparison preregistration. Standard-library Poisson recurrence removed that optional dependency.

User subsequently requested pure HAPPO versus full Sundial+LLM deployment. New protocol is separately registered under experiments/poisson_full_mechanism and docs/superpowers/specs/2026-10-17-poisson-full-mechanism-design.md. It has three new Poisson backgrounds with paired normal/shock, bothL,allfive seeds,120episodes; only30full-method shock episodes may call API,480HTTP/240semantic cap with no automatic retries. Offline fixtures are synthetic replies and do not establish efficacy. No historical paused API experiment is resumed.
