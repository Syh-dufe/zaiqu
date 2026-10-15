# Pure HAPPO missing-score audit recovery

The v2 seed11 simulation completed8 episodes4800 rows/API0 and all earlier
raw cost/model/action/prefix checks, then its audit tried reading scores.json.
The frozen evaluator only writes that file when a decision score exists; pure
HAPPO creates none. Preserve v2 failure and all raw files. No result-based change.

Independent recovery permits an absent scores.json only alongside zero calls,
zero generation events, zero runtime failures and all actions equal proposals.
All other original audits remain exact. Copy and re-audit seed11 (no simulation
rerun), run seed12 only, same source/paths/models/9600 total rows. Bind prior
source registration and every previous raw file, verify before/after. API0 and
network forbidden. No edits to frozen run.py. Archive this correction and failure.
