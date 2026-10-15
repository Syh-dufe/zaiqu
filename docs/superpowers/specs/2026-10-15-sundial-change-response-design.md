# Causal change-response adapter: approved replacement design

User chose demand-change response after stopping uniform allocation. Restore
original random integer allocation. Freeze HAPPO, Sundial and multiscale24.
No real event type/onset/end, future demand or test costs enter deployment.

At each forecast use delivered block means b only. If fewer than4 reports,
state=flat. Otherwise z=(last-mean(previous3))/max(1,std(previous10)). Up if
z>0.5, down if z<-0.5, flat otherwise. For the32 adapted draws in forecast
block j compute mu_j and shift all samples by
clip(lambda_state *3/(3+report_age)*(last-mu_j),-4,4), then clip0..20.
This changes location while preserving deviations before clipping; it does not
deliberately shrink sample spread. Retain exact original sampling seeds,
random integer allocation, age cropping,3+3 draw indices and selector budgets.

Five fixed candidates (up,down,flat lambdas):
zero=(0,0,0), all_half=(.5,.5,.5), up_half=(.5,0,0),
down_half=(0,.5,0), change_half=(.5,.5,0). No adaptive grid expansion.
No network, neural training or LLM replies. Same rule for all four types.

StageA cost calibration uses four stationary shock paths: first train path per
type in frozen multiscale adapter inputs. Models11,14 are a predeclared small
calibration subset, not selected by this new result. Five candidates x two
models x four types x normal/shock=80 episodes48000 node-periods,10 tasks,
max2 independent processes. These are adapter training paths now declared cost
development, not unseen confirmation. Prior four exposed test paths excluded.
Select lowest equally weighted shock mean over all8model/path cells; tie uses
candidate order above. Baseline included. Continue only if nonzero candidate
beats zero by at least1%; otherwise report and stop this version without tuning.

Reserve first dev path per stationary shock type for later cost validation;
it was previously adapter development, so never label it globally unseen.
No validation fitting now. If stageA passes, a separate frozen stageB protocol
must compare selected/zero/Merton on all five models and all four reserved paths
before any unseen confirmation; no models dropped. No automatic paid tasks.

Preserve all rows, costs, model hashes, forecast responses, failures and partial
attempts. Independent audits reconstruct causal state, exact shift, old/new
samples and random integer allocation, demand indices, report timing and base/
pre-notice zero actions. Stop on unexpected failures without overwriting or
changing frozen audit. No claim of cost improvement until complete independent
cost recomputation. User-facing results costs only; internal constraints remain.
