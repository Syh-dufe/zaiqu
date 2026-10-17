# Poisson Base-stock without review-period range extension

User explicitly requested removing our extension and following the paper. Use only Appendix E's lead-time-based bound construction, with the previously user-specified Poisson mean10 and existing physical environment. Do not silently change lambda or copy the paper's numerical targets under an unidentified original mean.

For stage i=1..3, cumulative lead-time demand is Poisson(10*i*L), lower probability=(4-i)/4 and upper=(4-i)/(5-i). Retain the registered discrete lower-end convention max(0,ppf(lower)-1), upper=ppf(upper), inclusive. This is the prior r=0 subset, with no r=1 review-period addition. Enumerate nondecreasing echelon targets and convert by successive differences to installation targets. Select lowest mean cost on the original20 baseline_development paths; lexicographic target tie-break. Cross-check against the already persisted paper_grid_best, which predates these shock results. No new outcome-based tuning.

Evaluate deterministic Base-stock on the original20 normal holdout paths and three exposed base/shock pairs at each lead:52 episodes31200 node-periods, API0. Reuse five-model HAPPO on holdout and both pure/full on shock comparison; do not retrain or rerun LLM. Scope is retrospective development comparison after user-requested restriction, not new confirmation. Preserve all extended-range results and all unfavorable outcomes.

Physical empty initial state, costs[1,1,1]/[1,0,0], orders0..20, supplier outstanding ledger and decision timing remain frozen. Thus this follows the paper's range construction, not an exact numerical reproduction or a proof of optimality in our action-limited environment.
