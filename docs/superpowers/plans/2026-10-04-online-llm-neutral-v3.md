# Neutral Format v3 Implementation Plan

> **For agentic workers:** Use subagent-driven-development to implement and independently review before registration. No unit tests are requested; compile, static review, no-API registration and the authorized research evaluation provide the checks.

**Goal:** Continue the approved format-only iteration with no elite retention and measure whether removing directive examples preserves useful original feedback behavior.

**Architecture:** New isolated experiments/online_llm_neutral package reuses the frozen original Client/EventController and strict v2 client. Four methods: happo, online_feedback, contract_feedback, neutral_feedback. All LLM methods use original event control (candidate0 replacement, no carryover); only output system prompt differs. Old registered source, input and outputs remain intact.

**Tech Stack:** Existing Python3.12 venv, torch CPU, original author environment and DeepSeek API.

## Diagnosis and selected approach

Observed on128 valid returned candidates per original/format method: original55 used3 rules versus format106; original80 mentioned agent versus format117. On96 common observed node states, original changed6013/12288 orders versus format4639/12288. These descriptive probes are not outcomes or independent causal proof. Lowercase true and too many rules remain real format constraints; do not normalize DSL to silently change meaning.

Three options considered: retain strict directed examples; use a neutral syntax appendix; change search/feedback budgets. Select neutral syntax appendix to isolate prompt steering without modifying search or control. No performance guarantee.

## Task1: Implement isolated package

- [ ] Create experiments/online_llm_neutral/client.py,controller.py,run.py,batch.py,analyze.py using v2 scaffolding. Use independent module aliases; do not patch globals of original or registered v2 modules.
- [ ] Original method uses original Client and original SYSTEM verbatim. contract_feedback uses v2 strict client and exact v2 FORMAT_SYSTEM. neutral_feedback uses same strict client with original SYSTEM plus appendix below. All three use original EventController, record correct group/method labels.
- [ ] Neutral appendix: exactly candidates top-level; exactly candidate_count candidate objects with explanation:string/rules:array;1..4 total rules per candidate; each rule exactly when/delta expression strings; legal features agent,inventory,backlog,pipeline,arrival,incoming,recent,baseline,growth,happo; Python True/False,and/or/not inside strings; original min/max/abs and bounds. No numerical rule examples, recommendation of three rules, preferred agent guards, preferred correction magnitude or zero-rule example. Error repairs apply the same neutral appendix, not v2 directed examples.
- [ ] Audit actual request SYSTEM and all input/model/source hashes. All initial calls ask3 candidates, one revision asks1; no retained candidate, protection or execution carryover path. Remove v2 elite-only audits. Preserve original forecast, independence, candidate count, expiry, budget, trigger and memory behavior.

## Task2: Fixed development batch

- [ ] Register two frozen models11/12; four fixed new traces generated demand20271101/event20271102; same two1.25/two1.5 strengths, start60..100,duration20..40, original truncation20. Freeze source/package/this plan/diagnosis before generating inputs. Preserve collisions and fail registration without resampling; retain unchanged own shock if present and report.
- [ ] Output results/online_llm_neutral/development_v3. Exclusive launch, no overwrite, serial two children. Expected64episodes38400rows;384HTTP maximum16 per shock episode, one format repair per semantic request. Authentication/balance/permission failures stop; no blind restart. Redact actual environment key.
- [ ] Analyzer recomputes raw metrics, causal reports, normal/pre-notification actions, complete six paired comparison matrices and all adverse pairs, tokens/format/transport/execution failures. Mean cost below originalfeedback and backlog no higher over8 developer pairs is consideration only, no automatic adoption or significance claim.

## Task3: Review, register and launch

- [ ] Compile new files, independent static review, then no-API preflight. Check snapshots and source equality before any paid calls. Commit/push source and protocol before launch.
- [ ] Launch once using configured existing venv and user environment key without printing it. Check actual PID/progress and first output. Restore half-hour heartbeat quiet unless meaningful progress/failure/completion.
- [ ] Write separate launch doc outside frozen plan/package. No changes to frozen source while running. No HAPPO training, no old experiment restart, no random method.

## Task4: Finish

- [ ] Independently audit all64 episodes38400rows, archive raw records with gzip lossless hashes, report all seed/path pairs and costs/API usage, commit/push. Pause follow-up after complete report.
- [ ] Any further mechanism needs development registration. Independent confirmation freezes selected prompt first and generates unseen paths; this batch and all historical test inputs are development evidence, not new confirmation.
