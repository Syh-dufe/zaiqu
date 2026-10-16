# Poisson HAPPO five-seed experiment

## Authorization and scope
User selected the paper-inspired Poisson optimality experiment, explicitly fixed lambda=10, five seeds, and lead times 2 and 4, and requested training to start. This is an adapted reproduction, not an exact numerical reproduction or a proof of optimality. No LLM, Sundial, paid API, or old paused task is involved.

## Frozen design
- Ten fresh policies: lead time 2 and 4, seeds 11 through 15 for each. Retain every seed and stopping reason.
- Three serial echelons; independent Poisson(10) external demand each period, no clipping and no added shock. Action is an integer 0 through 20, explicitly a capacity restriction relative to uncapacitated theory.
- Episode length 200, five training environments, initial inventory/backlog/pipeline all zero. Zero initial pipeline is an explicit implementation assumption.
- Holding coefficients [1,1,1], backlog coefficients [1,0,0]; no fixed ordering cost, price discount, shipping loss, or lost sales.
- Training reward follows the paper's local-plus-total equation with alpha=0.5, not the public implementation's local-plus-mean variant. Evaluation uses unblended raw costs, reported per echelon per period. These settings differ from earlier Merton training and those weights are not reused.
- Unchanged author HAPPO network, GRU, PPO optimizer and sequential factor update. Local observation L+3 and centralized critic 3*(L+3). CPU, one Torch thread; serial jobs because free memory is limited.
- At most 3,000,000 environment steps per job. Original validation every five 1,000-step rollouts, original warmup and patience=10. Early stopping is not a convergence claim. No empirical-stability stopping or favorable-seed selection.
- Twenty new validation trajectories shared across all jobs; separate twenty development trajectories reserved for later Base-stock calibration. Generate once after source freeze using seeds 20275001/20275002, reject within-split and cross-split identical sequences. No holdout is evaluated during training. Holdout generation/evaluation requires a subsequent frozen baseline comparison implementation.
- Best means the actual scheduled model saved by the original runner. Final checkpoint is separately saved and never relabeled best. Reload both and reproduce validation cost, verify tensor and file SHA.

## Audits and failure behavior
Every environment transition is checked against an independent scalar inventory/pipeline/backlog/cost implementation. Record all generated training demand trajectories, evaluation curve, exact configuration, update counts, architecture, model SHA, wall time, terminal reason. Check raw training cost against mixed rewards. Source hashes are checked before and after every job. Exclusive permanent lock; failures preserve diagnostics and stop dispatch, no automatic overwrite or retry.

## Base-stock interpretation
Do not use the old rolling-window z baseline as a theoretical optimum. Paper-reported targets must not be reused with lambda=10. A later comparison will recompute an appropriate reference on development inputs and freeze it before fresh holdout evaluation. Action capacity and finite-horizon startup prevent an automatic global-optimality claim.

## Publication
Register source/input hashes, explicit assumptions, fixture outputs and budget before formal launch. Preserve original author tracked files. Archive reproducible original bytes with gzip/SHA, verify Git blobs and push. Large intermediate weights remain local if omitted from Git and this must be stated. No prediction of superiority is registered.
