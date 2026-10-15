# Four-shock Sundial adaptation: first controlled allocation step

User approved the staged optimization on2026-10-15: allocation, causal change
features, then cost-aware calibration. Begin only with allocation isolation.
Keep frozen HAPPO11..15, Sundial pretrained model, multiscale24 adapter, original
report timing/notification, deterministic candidate construction and scoring.
Do not use the true shock label in deployment. Four labels only select physical
evaluation traces and organize results. API0, no training or LLM reply replay.

Compare existing adapted random allocation against new balanced allocation of
the SAME rounded three-period block total. For totalK use floor(K/3) each slot,
put remaining1/2 units into consecutive slots rotated by(block index+draw index)
mod3. Each slot differs by at most1; exact totalK, action demand bounds0..20,
age cropping, original3+3 draw indices and all32 original samples are preserved.
Rotation prevents always privileging the first slot; it does not reconstruct
unobserved actual within-block demand. This is a diagnostic comparator, not an
assertion that smooth physical demand is true. No distribution calibration is
trained in this step. Preserve original block samples and parameter SHA.

Run balanced adapted only on five models x four existing exposed physical paths
x normal/shock=40 new episodes24000 node-periods,20 serial tasks. Reuse all
previous random adapted, nativeSundial and Merton outputs unchanged, SHA-bound.
No new path generation, hyperparameter search or seed/type selection. Main
development comparison balanced minus random-adapted mean cost; Merton/native
are reference. Report all20 paired cells, per-type means, full200-period and
normal results, all unfavorable outcomes. Internal constraints stay audited;
user-facing report is cost only. No significance/generalization claim for four
exposed physical paths. Do not automatically adopt after a favorable mean.

Audit exact rounded totals/balance/rotation/cropping and32 path identities, raw
samples and selected block values reconstruct the frozen adapter, deployed3+3
matches generated paths, no future/report leakage, actual orders/cost/model
hash and normal/pre-notice agreement with original runs. Preserve any failure
and stop without overwrite or modifying frozen audit. Later change-feature or
cost-training steps require separate frozen implementation and protocol, using
independent training/development inputs; never tune these four paths to win.
