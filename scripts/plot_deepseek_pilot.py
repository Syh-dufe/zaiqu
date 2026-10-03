"""Display every pilot trace, without filtering rules or unfavourable cases."""
import argparse
import csv
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    directory=parser.parse_args().directory
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    records=list(csv.DictReader((directory/"metrics.csv").open()))
    groups=("happo","manual","deepseek")
    fig,axes=plt.subplots(2,2,figsize=(10,7),constrained_layout=True)
    for row,scenario in enumerate(("base","shock")):
        for col,metric in enumerate(("mean_cost","mean_backlog")):
            ax=axes[row,col]
            for index,group in enumerate(groups):
                values=[float(r[metric]) for r in records if r["group"]==group and r["scenario"]==scenario]
                assert len(values)==5
                ax.bar(index,np.mean(values),color=("tab:blue","tab:green","tab:orange")[index],alpha=.55)
                ax.scatter(index+np.linspace(-.12,.12,5),values,color="black",s=20,zorder=3)
            ax.set_xticks(range(3),["HAPPO","+ manual","+ DeepSeek"])
            ax.set(title=f"{scenario}: {metric}",ylabel="Per-node period cost" if metric=="mean_cost" else "Downstream mean backlog")
            ax.grid(axis="y",alpha=.25)
    fig.suptitle("DeepSeek pilot — frozen HAPPO — 5 traces; dots show every trace")
    for extension in ("png","pdf"):
        fig.savefig(directory/f"deepseek_pilot.{extension}",dpi=180)
    plt.close(fig)


if __name__=="__main__": main()
