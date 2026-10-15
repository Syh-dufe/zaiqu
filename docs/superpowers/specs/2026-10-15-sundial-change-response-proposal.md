# Replacement proposal: causal demand-change response

Uniform allocation was stopped by user; keep original random allocation for the
replacement. Prior user-approved roadmap includes causal change features and
cost-driven calibration. This document makes the next alternative reviewable;
it is not an implementation freeze or claim that a new experiment has started.

## Recommended minimal candidate

Keep frozen Sundial, multiscale24 and HAPPO. Add a bounded residual response that
mixes adapted Sundial block forecasts with the latest delivered report level.
Use only report-history features: current-vs-recent level contrast, signed recent
change and time since last report. A causal gate adjusts mix strength separately
for observed upward/downward/approximately flat changes; never feed true event
type, actual onset/end, hidden future demand or retrospective outcome at deploy.
The same resulting module applies to all four shock types; no per-test-type
model switch. The purpose is responsiveness, not assuming future peaks/endings.

Before choosing coefficients, fix the causal state definition, small candidate
bank, training/development path split and total simulation budget. Zero response
must remain an explicit baseline. Select response coefficients using development
closed-loop I+B rather than only forecast error. Existing adapter-training paths
may be reused as declared development (not new confirmation); keep prior four
exposed cost paths out of selection. Preserve original block distribution and
random integer allocation. No API or HAPPO/Sundial retraining.

## Alternative

Directly calibrate the existing24 parameters against decision-cost ranking on
training states, using true futures as training labels only and independent
development. This addresses objective mismatch more directly but requires a
larger and more complex training/audit pipeline. Do not add both interventions
at once: their marginal contributions would be unclear.

## Scope boundary

The exact small response candidate bank and full cost budget must be preregistered
in the implementation plan after design choice, before any fitting or evaluation.
All seeds and four types retained; final frozen model needs new unseen-path
confirmation. No promise of improvement, no tuning old test paths until winning.
