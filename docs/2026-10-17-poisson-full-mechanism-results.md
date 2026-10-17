# Poisson: frozen HAPPO versus full Sundial-LLM mechanism

## Completed scope
Ten jobs,120episodes72000node-periods; five trained seeds11..15 at L2/L4, pure HAPPO and full six-rule response-all-half Sundial/LLM strategy, three new common demand paths with paired normal/shock. Both methods share exactly the same best weights, zero initial inventory/pipeline, h=[1,1,1],b=[1,0,0],200periods,actions0..20. Weights remain frozen. This is the deployed multiscale24/response adapter, not the failed later cost-adapter upgrade. This is a small development comparison of a complete system, not evidence solely for LLM semantics or Sundial versus Merton.

Physical background is independent Poisson10. Three profiles: single70..90×1.5; sustained60..110×1.25; double65..85/105..125×1.5 (zero-based, right-exclusive). Shock counts ceil(factor*base), without physical demand clipping. New reports and shadow clones correctly support Poisson counts, bothL,weighted costs. Forecast samples retain their legacy0..20cap; physical demand is unbounded, a disclosed mismatch. Exactly three independent background paths, one per type; five seeds are different models, not independent demand paths. No hidden type, strength, end time or future demand enters prompts. Delivered reports aggregate completed blocks of3; notice arrives onset+2. Normal execution and shock pre-notice execution match pure HAPPO.

## Realized shock average costs
Cost=sum realized weighted per-node inventory/backlog costs/(200*3). Lower is better. Each type/L row averages all five models on its one fixed path. Aggregate gives three types equal weight. Reduction=(pure-full)/pure.

|Lead|Type|Pure HAPPO|Full Sundial+LLM|Reduction|
|---|---|---:|---:|---:|
|2|Single surge|14.316333|14.288000|0.20%|
|2|Sustained surge|26.175667|14.610667|44.18%|
|2|Double surge|29.482333|15.478333|47.50%|
|2|Three-type mean|23.324778|14.792333|36.58%|
|4|Single surge|28.678667|25.136000|12.35%|
|4|Sustained surge|32.744000|23.840000|27.19%|
|4|Double surge|33.549667|32.416000|3.38%|
|4|Three-type mean|31.657444|27.130667|14.30%|

All six type/L mean contrasts favor the full method; L2single is almost unchanged. Do not call these independently significant or universal improvements.

## All seeds, including unfavorable results
Each row averages the three shock types.

|Lead|Seed|Pure|Full|Full relative change|
|---|---:|---:|---:|---:|
|2|11|19.802222|18.132222|-8.43%|
|2|12|30.563889|10.266111|-66.41%|
|2|13|30.860556|23.163333|-24.94%|
|2|14|14.988333|10.653333|-28.92%|
|2|15|20.408889|11.746667|-42.44%|
|4|11|34.491111|33.192778|-3.76%|
|4|12|38.112778|29.623333|-22.27%|
|4|13|17.356111|14.908889|-14.10%|
|4|14|31.218333|19.333889|-38.07%|
|4|15|37.108889|38.594444|+4.00%|

Across30seed×type×L shock pairs:23improve,6worsen,1tie. AtL2,12improve/3worsen; atL4,11improve/3worsen/1tie. Seed15atL4worsens on the three-type mean. All normal means and paired action traces agree, so paired difference-in-differences equals shock difference in this batch. Raw unfavorable cases, rules, rejected revisions/reviews and API failures remain archived. The base HAPPO training was unstable and did not approach the separately calibrated stationary Base-stock reference; this deployment benefit does not establish superiority over a fully trained optimal reference.

## Audit and actual API accounting
Original network failure at L2seed11:19physicalHTTP/15semantic attempts;14successful semantic stages,18physical rows including format repairs. User requested continuation. Exact SYSTEM/identity/full request matching reused those18records without charging them again. Offline replay reproduced all6231old persisted rows, including partial episode; synthetic later replies were fixture only. Recoveryv1offline missing-input mapping failed atAPI0; v2corrected root mapping in an independent wrapper. No model, prompt, parser, scorer, selection threshold or input was changed for continuation.

Complete physical accounting, counting old records once:290HTTP/241semantic attempts, comprising old19/15plus new271/226. There are240successful semantic stages; one additional semantic attempt was the original failed transport request.241cap was transparently registered for manual recovery; HTTP remains below480. Cached records in first new task are logical execution records and are excluded from new physical cost, not double counted. No claim that the original failed prefix was free. Recorded usage and all raw responses remain available; missing usage on the transport failure is not assumed to mean no server cost.

Original immutable audit passed for every task and was rerun across all72000persisted rows: raw weighted costs, inventory/pipeline/backlog transitions, per-case actions, unique identities, normal/pre-notice and own pre-shock prefixes, causal report timing/content, API attribution and budgets. Source and all registered model file hashes verified. Per-task before/after tensor hashes confirm no actor/critic or Sundial updates. Separate final accounting reconciles all job ledgers and all30pairs.

## Artifacts and conclusion
- Source: experiments/poisson_full_mechanism and independent network continuation wrappers; registrations5a907ca/b51e9ba.
- Original failed root: results/poisson_full_mechanism/v1 (preserved).
- Final root: results/poisson_full_mechanism/network_recovery_v2 (completed).
- Original/failure/fixture preregistration: docs/artifacts/poisson_full_mechanism_preregistration and docs/artifacts/poisson_network_recovery_v2_preregistration.
- All final originals: docs/artifacts/poisson_network_recovery_completed,161original files+manifest, lossless gzip and per-file SHA. Final tables/accounting/report captured in a separate addendum, retaining the original completion archive unchanged. Cached Sundial large weights remain local; published pinned revision/SHA, not a claim that all pretrained weight bytes are on GitHub.

Conclusion: on these three new Poisson-background shock paths, the full mechanism reduces mean cost relative to the ten frozen base policies, with variable benefit byL/type and six unfavorable individual pairs. Further independent paths and controlled component/information/compute comparisons are required before broad superiority or causal attribution claims. No automatic new experimental optimization or extra paid batch follows this result.
