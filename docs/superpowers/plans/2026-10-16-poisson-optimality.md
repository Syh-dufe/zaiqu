# Poisson five-seed training implementation plan

**Goal:** Start and audit ten fresh HAPPO training runs for Poisson(10), lead times 2/4, seeds11..15, API0.

**Architecture:** New isolated experiment modules adapt only environment globals and reward processing in process. The original author runner and sequential update remain unchanged; passive observation records validation, training cost, best/final checkpoints and independent transition checks. A serial driver verifies frozen hashes and stops at the first failure.

**Tech stack:** Existing Python/PyTorch CPU runtime, NumPy, author HAPPO, standard-library JSON/SHA/gzip/subprocess.

## Execution checklist
- [ ] Create common configuration, SHA/JSON helpers and isolated environment adapter; independently recompute every transition.
- [ ] Create training observer using original runner, with raw-cost reconciliation, actual saved-best metadata and final/best reload verification.
- [ ] Create permanent-lock batch driver with fixed ten-job queue, source verification and immutable failure records.
- [ ] Freeze source before generating twenty validation and twenty baseline-development paths. Check sequence identity within and across splits.
- [ ] Run 1,000-step fixtures for each lead time in separate fixture directories; verify dimensions, all three agent updates, mixed reward reconciliation and best/final handling. Fixtures are excluded from formal results.
- [ ] Register all original author Python sources, new sources, protocols, input files and fixture outputs; archive gzip and verify original SHA and absence of User API key; commit/push and compare stored Git blobs.
- [ ] Launch one hidden unique driver with stdout/stderr redirection and launch metadata. Confirm live process and first formal curve row before claiming training started.
- [ ] After all jobs finish, independently audit curves, models, raw costs and source hashes; archive outcomes and update report/README. Base-stock holdout comparison follows a separate frozen implementation, without changing these training results.

User has approved execution and parameter choices in this chat. No additional confirmation is required for routine implementation or launch. No old stopped API task is resumed.
