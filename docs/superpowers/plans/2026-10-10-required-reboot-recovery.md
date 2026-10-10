# Required experiment continuation after computer reboot

The computer boot time observed on 2026-10-10 was 01:02:18. The original required-package driver and the no-API upgrade fixture both disappeared. Files being written in the current task contain null bytes. This is not an API quota failure or evidence of algorithm performance.

## Preserved evidence and eligibility

`results/reboot_diagnosis/20261010_v1` preserves every file of the interrupted confirmation10_main_seed11 and offline_fixture_v1, plus progress and attempts, as lossless gzip with hashes. All 47 completed task markers, 470 audited raw files and frozen original source hashes were checked: zero mismatches. The unfinished confirmation task has no completed marker and is excluded entirely from performance estimates. Its unreadable request records cannot be reconstructed: request count and tokens remain unknown.

## Recovery policy

Run only the independent `experiments/submission_required_reboot_recovery/resume.py`. Reuse completed tasks without new simulation or API. Repeat the single interrupted task exactly once into `_crash_replay1`; old partial output is never overwritten. Retain all remaining preregistered tasks, methods, inputs, models, prompts, selection rules, statistics and seeds. No score-dependent choice is made. A second crash or any program/audit error stops for diagnosis. A quota failure on the crash replay stops; other future tasks retain their original single quota-recovery allowance.

Reserve the interrupted task's entire registered upper bound of 176 HTTP and 88 semantic requests against the original cumulative batch caps. These are conservative budget reservations, not observed calls. Keep them separate from readable HTTP/tokens summaries. Cumulative phase caps remain 17600/8800 for confirmation and 16000/8000 for sensitivity. No new cap is added. Remaining performance comparison and bootstrap are unchanged.

Resource summaries include all readable attempts and explicitly disclose missing interrupted HTTP/token records; never claim complete request retention. The damaged files themselves remain preserved. Original source files are not edited: asserted isolated run adaptations skip completed tasks/phases, use a new permanent launch lock, conservatively account for the interrupted attempt, and isolate resource parsing from corrupted files.

## Before first paid replay

Check original frozen contracts, every completed marker and raw hash, diagnosis preservation and source hashes. Capture the isolated adapted run hash, recovery code and protocol hashes and all reused task identities. Commit and push the recovery registration with exact Git-byte preservation, then launch one hidden background driver. No duplicate process may exist.

## Upgrade fixture

The independent no-API fixture v1 also suffered null-filled unfinished files. Its records are preserved and never used as performance evidence. A bare auditor import was independently found to resolve the prior experiment's module after inherited sys.path changes. The v2 fixture and upgrade driver use explicit file-path auditor loading. Run v2 into a fresh directory with networking forbidden; this does not change the original paid experiment or its methods.

## After completion

Independently audit all 4480 episodes and 2688000 node-periods, unchanged formal statistics and all actual readable costs. Archive original quota attempts, interrupted crash outputs and the crash replay. Disclose unknown interrupted request usage. Only after full review, lossless archival and publication write the upgrade-release checkpoint and permit the guarded/pool paid development batch.
