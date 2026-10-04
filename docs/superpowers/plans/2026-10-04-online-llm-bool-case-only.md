# Boolean Case Only Development Plan

User authorizes only lowercase boolean compatibility on original realtime LLM. No prompt, network, candidate, event, forecasting, selection, actor or environment change.

## Fixed design

- New isolated experiments/online_llm_case_only package; preserve all old registered source/results.
- Load original Client twice with distinct module aliases. Baseline keeps original compile_rule. Compatibility alias replaces only its compile_rule reference with a wrapper; Client.generate body stays byte-for-byte original source, including initial/repair requests and errors other than repaired boolean names.
- Wrapper deep-copies candidate and tokenizes only when/delta expression strings. Replace only NAME tokens exactly true/false with True/False. Preserve every other byte via reverse source-span edits; do not change identifiers, quoted strings, explanations or JSON. Original parser still enforces all size/AST/bounds constraints. Unknown names and unsupported expressions still fail. Normal already-valid expressions and compiled semantics unchanged.
- Raw replies/candidates remain original. Return compiled repaired AST to the original controller; record offline normalization audit and raw hashes separately. No hidden normalization in baseline.
- First replay archived replies (original development_v1, confirmation_v1 and targeted/neutral development): count previously failing candidates rescued, ensure other errors retained, and verify already-valid AST equivalence. This is parsing audit only, not counterfactual performance.
- Small closed-loop comparison: reuse the exact development_v3 four paths deliberately as development; seeds11/12; three groups happo/online_feedback/case_feedback; normal/shock=48episodes28800nodeperiods. This avoids changing disaster inputs when testing the single parser change. Independent API draws mean this is not an identical-generated-output comparison; report stochastic limitation.
- Same original SYSTEM for both LLM groups, original Client transport/repair text, original EventController and candidate0 replacement/no carryover, all original budgets. Maximum256HTTP total16 per shock episode. HAPPO frozen, no DeepSeek training. Record raw information/model/source/protocol hashes and both request SYSTEM equality. No random methods.
- Freeze before launch/copying fixed reference inputs; assert reference hash equals neutral v3 manifest; no new test claim or collision resampling. Output results/online_llm_case_only/development_v1. Exclusive launch/nooverwrite/fatal auth stop.
- Complete raw cost/report/API/normal/pre-notification/model audits and three comparison matrices. Retain all pairs/negatives and count normalization use/remaining syntax failures/tokens/time. No guarantee repair improves cost; no automatic victory claim. New independent test required for final deployed version.

## Execution

- [ ] Implement five isolated client/controller/run/batch/analyze files, strict scope checks.
- [ ] Compile and independently review; no unit tests requested. Run authorized archived-output parsing audit, no API/rollout.
- [ ] Register no-API preflight; commit/push then launch once with existing Python3.12 venv and private user key.
- [ ] Monitor every30 minutes meaningful events only; no old experiment restart.
- [ ] Independently audit48/28800 and archive report/raw records. Complete pending neutral-v3 report separately, without changing its results. Pause follow-up after reports uploaded.
