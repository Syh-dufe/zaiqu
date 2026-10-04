# Targeted online LLM v2 implementation plan

> For agentic workers: use subagent-driven-development, with implementation and independent review checkpoints. User approved the diagnosis/design on2026-10-04. Research experiments and preflight are authorized; no separate unit tests requested.

**Goal:** Implement output-contract improvements and candidate retention, then launch the approved64-episode development experiment.

**Architecture:** New experiments/online_llm_targeted modules reuse the original environment, forecast/selector and model contracts; old online_llm and confirmation sources remain unchanged. Four methods: happo, online_feedback (unchangedv1), contract_feedback (format-only), elite_feedback (format plus retention). Each method retains causal episode-local state and identical scheduling/HTTP limits.

**Tech stack:** ExistingPython3.12 CPUtorch runtime and DeepSeek HTTP client. No HAPPO training.

## Tasks

- [ ] Create independent client/controller/run/batch/analyze modules under experiments/online_llm_targeted. Source hashing covers new modules and all reused frozen dependencies, excluding pycache.
- [ ] Keep v1 prompts, requests and behavior exact in online_feedback; strengthen schema examples/allowed features only for contract/elite. Invalid transport/authentication handling remains unchanged and all requests persist recursively redacted.
- [ ] In elite_feedback retain the last actually executed nonzero candidate across generation events. Capture before expiry resets chosen, re-score under current state; no automatic execution, no independent review scores sent to API. Generate2fresh if retaining1, else3fresh.
- [ ] Score3candidate+zero, protect best eligible search option (lowest-cost valid if none eligible); replace the weakest other candidate after a single revision. Same final3candidate count and independent review; failures preserve originals or logged zero fallback. Record retention/protected/replaced identities and all pre/post candidates.
- [ ] Register sources/models/runtime before generating4new paths with demand20271001/event20271002. Scan historic base/shock and cross-path collisions; own base==shock allowed. Preserve diagnostics and fail rather than resample. Inputs shared by seeds11/12 and all4methods.
- [ ] Freeze contracts and exclusive launch marker; serial2model runs,32episodes19200nodeperiods each, total64/38400. Originallibrary not a method. ThreeLLM methods at most16HTTP per shockepisode;384HTTP batchmaximum. Keep 4events,5periodscreening,3search+3review,20horizon5correction,1%/no-backlog-increase gates.
- [ ] Preflight compiles and validates every source/input/model contract without HTTP/environment rollouts. Independent static review verifies old behavior, causality, retention and replacement, request/forecast budgets and no random method.
- [ ] Commit/push after review and preflight, launch one hidden driver via existing configured runtime with key from User environment; no secret outputs. Check actualPID/progress/errors and update30minute monitor to this task.
- [ ] Complete raw audits, all method/model/path differences, formatting/revision/retention/fallback metrics and API/token/wall accounting. Development-only comparisons, no independent efficacy claims; alladverse results retained.
- [ ] Archive/report/push after completion; choose expansion using predeclared development criterion (costlower/no-backlogincrease vsoriginal feedback). Any independent confirmation must use new unseen paths after final mechanism freeze. No automatic tuning on old confirmation or resuming old training.

## Verification commands

Configured runtime: C:/Users/13384/.codex/worktrees/delivery-happo/新/.venv/Scripts/python.exe.

```powershell
& 'C:/Users/13384/.codex/worktrees/delivery-happo/新/.venv/Scripts/python.exe' -m py_compile experiments/online_llm_targeted/client.py experiments/online_llm_targeted/controller.py experiments/online_llm_targeted/run.py experiments/online_llm_targeted/batch.py experiments/online_llm_targeted/analyze.py
& 'C:/Users/13384/.codex/worktrees/delivery-happo/新/.venv/Scripts/python.exe' -u experiments/online_llm_targeted/batch.py --preflight
```

Expected: successful compilation; immutable64episode registration without API/evaluation. User environment key must be inherited privately for contracts and later launch. Registration/run refusal onexisting launch orfailure is required.
