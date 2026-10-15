# Change-response cost calibration implementation plan

Goal: select a small causal response by closed-loop cost, preserving original
random allocation and frozen HAPPO/Sundial/multiscale24. Design and all numerical
rules are in the matching design document; user explicitly chose this direction.

- [ ] Implement causal state/response and independent predictor wrapper.
- [ ] Copy first stationary train/dev path per shock type from registered adapter
  inputs into calibration/reserved files, preserve source identity/SHA and append
  only nonconsumed sentinel. Verify first200 no overlap with old four cost paths
  and no train/reserved overlap. No new random path generation.
- [ ] Implement all-four-type single-method runner, no network, unchanged actor.
- [ ] Independently audit transform/allocation, source/model/demand/report/rows,
  normal and pre-notice actual=proposal, calls0,4800 node-periods per task.
- [ ] Register10 tasks80 episodes48000 rows, fixed five candidates x models11,14,
  max2 processes; publish sources/inputs/models/configs and zero API budget before
  exclusive launch. Preserve logs and stop future dispatch after audit failure.
- [ ] Independently compute cost ranking and1% gate, preserve every candidate,
  archive exact bytes/credential absence/Git blobs, report README commit/push.
- [ ] Only after passing, separately freeze five-model validation of selected,
  zero and Merton on reserved dev paths. No tuning based on old exposed tests.
