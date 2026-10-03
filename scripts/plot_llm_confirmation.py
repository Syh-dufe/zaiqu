"""Plot all twenty paired cases and preregistered mean confidence intervals."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);root=parser.parse_args().directory
    summary=json.loads((root/'summary.json').read_text())
    rows=list(csv.DictReader((root/'paired.csv').open(encoding='utf-8')))
    groups=tuple(g for g in ('manual_screen','llm_single','llm_iterative') if g in summary['analysis'])
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for index,(ax,key,title) in enumerate(zip(axes,('cost_delta','backlog_delta'),('System cost difference','Downstream backlog difference'))):
        for x,group in enumerate(groups):
            a=summary['analysis'][group];ci=np.asarray(a['ci95'])[:,index];mean=a['mean_delta'][index]
            points=[float(r[key]) for r in rows if r['group']==group]
            assert len(points)==summary['n_demands']
            ax.scatter(x+np.linspace(-.12,.12,len(points)),points,s=15,alpha=.55)
            ax.errorbar(x,mean,yerr=np.asarray([[mean-ci[0]],[ci[1]-mean]]),color='black',fmt='s',capsize=5)
        ax.axhline(0,color='grey',linestyle='--');ax.set_xticks(range(len(groups)),groups,rotation=15)
        ax.set_title(title);ax.set_ylabel('Controller minus frozen HAPPO')
    fig.suptitle(f"Fixed v3: all {summary['n_demands']} new demand traces; paired mean and bootstrap 95% CI")
    fig.tight_layout();fig.savefig(root/'confirmation.png',dpi=200);fig.savefig(root/'confirmation.pdf');plt.close(fig)


if __name__=='__main__':main()
