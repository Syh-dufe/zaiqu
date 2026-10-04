"""Plot the fixed primary and descriptive secondary confirmation differences."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
source=ROOT/'results/online_llm/confirmation_v1/summary.json'
summary=json.loads(source.read_text(encoding='utf-8'))
comparisons=[('vs HAPPO',summary['primary'],'ci97p5'),
             ('vs old library',summary['secondary']['online_feedback_vs_llm_library'],'ci95'),
             ('vs one generation',summary['secondary']['online_feedback_vs_online_once'],'ci95'),
             ('vs random candidates',summary['secondary']['online_feedback_vs_random_screen'],'ci95')]
fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
for endpoint,ax in enumerate(axes):
    for index,(label,comparison,interval) in enumerate(comparisons):
        low,high=comparison[interval][0][endpoint],comparison[interval][1][endpoint]
        mean=comparison['mean_delta'][endpoint]
        color='#1d4ed8' if index==0 else '#6b7280'
        ax.errorbar(mean,index,xerr=[[mean-low],[high-mean]],fmt='o',color=color,capsize=4)
    ax.axvline(0,color='#9ca3af',linestyle='--',linewidth=1)
    ax.set_yticks(range(4),[c[0] for c in comparisons]);ax.invert_yaxis()
    ax.set_xlabel(('Mean cost difference','Mean downstream backlog difference')[endpoint])
    ax.set_title(('Cost','Downstream backlog')[endpoint])
    ax.grid(axis='x',alpha=.2)
fig.suptitle('Online feedback minus comparator: 5 frozen models x 20 new trajectories')
fig.supxlabel('Lower is better. Primary: 97.5% CI; secondary: descriptive 95% CI.')
out=ROOT/'docs/figures';out.mkdir(exist_ok=True)
for suffix in ('png','pdf'):
    fig.savefig(out/f'online-llm-confirmation-differences.{suffix}',dpi=200)
print('Confirmation difference figures saved')
