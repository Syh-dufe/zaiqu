# Periodic demand reports implementation plan

**Goal:** Add configurable periodic aggregate demand reports to the frozen-HAPPO operator-library evaluator without changing author inventory dynamics.

**Architecture:** A report stream observes completed local periods, releasing non-overlapping block means only after a full block. External rules and forecasts consume the delivered reconstructed history; local actors retain original observations. Default legacy mode bypasses reports. Forecast branches receive a public report state with unreported values replaced by a last-report estimate.

**Tech stack:** Existing Python, NumPy, PyTorch evaluator; no new dependency or API request.

- [x] Add `experiments/deepseek_refinement/reports.py`: period sequencing, aggregate delivery, public audit, and synthetic branch projection without pending real values.
- [x] Extend `shadow.py` forecasts with report age; extend score/select with optional projected report streams. Preserve legacy calls and full-history original-policy replay audits.
- [x] Extend `run.py` with optional `--report-interval {1,3,5}` in fixed-library mode only; route all external demand features through delivered reports, record every decision's available information and deliveries. Resolve library path before cwd changes. Use matching-count manual candidates under the new mode, with fixed documented strengths.
- [x] Document timing, permitted inventory/local-order information, predictor approximation, comparison budget, scope and exact commands. Keep seeds and prior results unchanged. Do not launch experiments or add/run tests for this implementation-only request.
- [x] Review source paths and diff for instantaneous-history leakage and backward compatibility, then commit and push the authorized project changes.
