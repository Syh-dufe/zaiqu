# Sundial without LLM: deterministic ordering cost development

User approved frozen HAPPO plus the same deterministic selector on 2026-10-15.

## Frozen design

Compare original Merton, native Sundial, and multiscale24 Sundial with identical
deterministic_search controller from submission_required/component.py. Enumerate
(-2,0,2)^3 corrections, deduplicate clipped actions, retain three by synthetic
search cost, evaluate six coordinate neighbors, then use the original independent
review and eligibility constraints. No LLM generation, replayed replies, prompts,
or API requests. This is the existing deterministic baseline, not guard_pool.
Each provider has the same 3 search / 3 review paths, horizon20, correction5,
four construction events and subsequent registered screening. Report timing,
notification and physical environment remain unchanged. Frozen HAPPO seeds14,15;
no model training. Sundial uses 16+16 draws and deploys original first3 per group;
the failed representative-path selector is excluded. New adapter is fixed before
this cost evaluation; no result-driven switching to crps24.

Reuse the same single double-surge physical path (trace2) and original forecast
stream identities b1_s{seed}_t2_p{period}. Three providers x two scenarios x two
model seeds = 12 episodes, 7200 unique node-period rows. This is exposed-path
development, not an independent confirmation or multiple independent paths.
Main outcome is full200-period mean I+B over3 nodes, and paired cost difference
multiscale24 minus Merton. Include native Sundial and every unfavorable result.
Old LLM costs may be displayed separately but do not isolate predictor effects.

## Implementation and execution

- [ ] Independent runner and controller injection; fail on any network attempt.
- [ ] Freeze source, input, adapter and actor/critic file SHA before execution.
- [ ] Persist registration and push before one exclusive batch launch.
- [ ] Run seed14 then15, preserve failures, never overwrite or blindly restart.
- [ ] Independently recompute all7200 row identities and I+B means; validate
  normal and pre-notice actions against historical HAPPO, report causality,
  unchanged model hashes, and zero calls. Save complete raw outputs and timing.
- [ ] Report cost only to user; archive failures and all negative findings.

Budget: 0 API / 0 semantic calls. CPU only. Existing paid experiment remains
blocked_service_outage with all timeout/partial files intact; do not resume it.
