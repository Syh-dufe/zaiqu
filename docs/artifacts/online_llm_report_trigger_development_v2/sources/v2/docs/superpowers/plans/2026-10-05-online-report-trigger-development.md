# Report-triggered online LLM development implementation plan

> **For agentic workers:** Use executing-plans to implement sequentially in the existing worktree. User has authorized continued implementation; no additional approval is needed. Do not dispatch new agents.

**Goal:** Compare a causal report-triggered generation schedule with original online_feedback under the same maximum API budget.

**Architecture:** Add separate controller, runner and batch files. Reuse frozen original API and selector; preserve original methods and raw v5b results. This version is development only on explicitly exposed inputs.

**Tech Stack:** Project Python3.12, PyTorch2.14.1+cpu, original DeepSeek Client, JSON/CSV/SHA256 auditing.

Specification: [complete design](../specs/2026-10-05-online-report-trigger-design.md).

## 1. Register scope and input roles

- [x] Complete v5b audit/report/archive and push before modifying any method.
- [x] Fix development inputs to existing batch01 and batch06, all five models, three methods and 240 episodes.
- [ ] Write a development role manifest listing original paths and SHA256, first200 consumed path hashes, all training contracts, original SYSTEM SHA, runtime, method set and API ceilings. Link v5b verification and this spec; do not edit v5b artifacts.
- [ ] Capture frozen hashes of the new three files, this plan/spec, original runner/client/controller/dependencies, source-input-library-model metadata. Refuse existing output.

## 2. Controller

Create `experiments/online_llm_report_trigger/controller.py`. Keep original decide body byte-identical apart from the trigger block plus schedule diagnostic fields. Original methods must use imported original EventController.

- [ ] Load original controller explicitly under a unique module name; preserve inherited fields and reset semantics.
- [ ] Calculate latest two demand_mean report average only from reports.deliveries. Add per-episode last_generation_period/reference_mean.
- [ ] Use slot/new_report from original. For event0 generate normally; for later events require gap>=20 and (relative_change>=0.25 or gap>=30). Set generation clock/reference only after trigger. Never use hidden event type or future demand.
- [ ] Leave generation, repair, index0 replacement, forecasts, score, independent review, expiry and memory paths identical. Add schedule audit to each screening/generation record without feeding it into the prompt.
- [ ] Preflight synthetic report timelines at boundaries19/20/29/30 periods; verify only legal slots/new reports, four-event cap and episode reset. User authorized verification; no API in these checks.

## 3. Runner and batch

Create `experiments/online_llm_report_trigger/run.py` using the frozen v5 runner structure and original input validation. Three METHODS; original HAPPO/online_feedback dispatch directly to original controller, new method dispatch to independent newcontroller with Client using SYSTEM unchanged. Refactor or copy evaluate only as needed; source-compare original group behavior.

Create `experiments/online_llm_report_trigger/batch.py`. Ten seed×batch tasks, sequential. Output `results/online_llm_report_trigger/development_v1`. Preserve original input labels01/06 and local trace forecast seeds. Each task24 episodes/14,400 rows. Caller never receives evaluation results for prompt tuning.

- [ ] Register before launch, verify all contracts, noAPIpreflight all10 tasks.
- [ ] Validate expected methods in completed parameter_checks; do not copy the old two-method assertion unchanged. Total240 episodes/144,000 rows.
- [ ] Retain calls/episodes/scores/periods/reports/failures and logs. Account all attempts, per-episode caps and total budgets. Carry over quota-wait and one retry per task policy, preserving failed attempt dirs.
- [ ] Commit and push registration/source, then start exactly one hidden driver with the configured venv and Windows User credentials; save launch PIDs and progress. Do not run any old experiment.

## 4. Independent result audit

- [ ] Recompute240 episodes and unique144,000 nodes from CSV; verify input transforms, model/source hashes, notification timing and normal/pre-notification invariance.
- [ ] Verify each new generation clock/reference/report threshold independently from delivered-report records. Document original fixed times vs new times and actual call counts.
- [ ] Compute original-vs-new paired costs/backlogs, per type/seed and all regressions. Report costs against HAPPO as secondary. Keep API nondeterminism limitation.
- [ ] Apply fixed development gate in design; no significant/generalization claim, no hidden threshold adjustment.
- [ ] Add new lossless archive helper, byte-preserving .gitattributes and force-add any ignored logs/source snapshots only after credential absence check. Verify Git stored blobs against export SHA; update README/report; push.
- [ ] If gate passes, freeze method then preregister fresh confirmation paths; otherwise diagnose and report before considering any separately registered next version. Keep the automation active for the user-authorized sequence.
