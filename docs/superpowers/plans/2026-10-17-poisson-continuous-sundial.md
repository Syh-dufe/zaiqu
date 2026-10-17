# Continuous Poisson Sundial pilot plan

**Goal:** Compare a report-synchronized Sundial plus periodically refreshed LLM policy with pure HAPPO on matching unshocked Poisson paths.

**Architecture:** New runner copies the frozen evaluator body into an isolated namespace, supplies a controller source variant for periodic LLM refresh and per-report screening, and adds an independent audit and one-shot serial driver.

**Protocol:** Two development paths, five frozen model seeds, two lead times, forty paired episodes, 24,000 node-periods, 320 HTTP/160 semantic hard cap, API0 fixtures. Development only, not unseen confirmation.

1. Freeze source/spec/plan, paths, weights, predictor/adapter and budget hashes. Commit and attempt bounded push before any real API call.
2. Run two API-free synthetic-rule fixtures and independently verify continuous report forecast/screen cadence, four scheduled refreshes, raw inventory, cost, corrections, hashes and no event notices.
3. Run the ten real serial tasks with no automatic retries; preserve partial outputs/errors and API tokens.
4. Independently recompute all forty episodes, report cost and API usage; archive original bytes, verify gzip/SHA/Git blobs, publish report and push.
