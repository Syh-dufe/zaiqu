# Balanced allocation development implementation plan

Goal: isolate report-block allocation effect before adding more adaptation.
Architecture: new predictor wrapper delegates all raw forecasts and multiscale24
transform to frozen code and only replaces integer block allocation. Independent
runner narrows to adapted variant, retaining original trace identities. New
exclusive driver freezes dependencies and old results, audits each task, then
archives all outcomes. Existing experiment source/inputs remain untouched.

- [ ] Implement predictor with exact total-preserving balanced slot allocation.
- [ ] Implement trace0..3 single-method runner with no network/client generation.
- [ ] Independently audit allocation and original adapter outputs, cost rows,
  model hashes, reports, old normal/pre-notice rows; no unavailable references.
- [ ] Register20 tasks40 episodes24000 rows, all11..15/trace0..3, zero API;
  publish source/input/model/old-results hashes before exclusive serial launch.
- [ ] Complete all tasks, preserve diagnostics and negatives on failure.
- [ ] Independently recompute final means/cost changes, archive exact bytes,
  scan User credential absence, verify Git blobs, README/report commit/push.

Scope and acceptance follow the approved design document. No new HAPPO training,
Sundial fine-tuning, feature additions, representative-path selection, paid API,
new confirmation input or result-based model switching in this phase.
