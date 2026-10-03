"""Plot all twenty paired traces as mean demand and downstream backlog curves."""
import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    directory = parser.parse_args().directory
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    demands = json.loads((directory / "demands.json").read_text())
    records = list(csv.DictReader((directory / "periods.csv").open()))
    fig, grid = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    axes = grid.ravel()
    periods = np.arange(1, 201)
    for scenario, color in (("base", "tab:blue"), ("shock", "tab:orange")):
        axes[0].plot(periods, np.mean(np.array(demands[f"{scenario}_traces"])[:,:200], axis=0),
                     label=scenario, color=color)
    axes[0].set(title="Mean demand", ylabel="Demand units per period")
    for axis, model in zip(axes[1:], ("official_best", "final")):
        for scenario, color in (("base", "tab:blue"), ("shock", "tab:orange")):
            selected = [r for r in records if r["model"] == model and r["scenario"] == scenario and r["node"] == "0"]
            curve = np.array([float(r["backlog"]) for r in selected]).reshape(20,200).mean(axis=0)
            axis.plot(periods, curve, label=scenario, color=color)
        axis.set(title=f"Downstream backlog: {model}", ylabel="Backlogged units (mean of 20 traces)")
    for model, style in (("official_best", "-"), ("final", "--")):
        for scenario, color in (("base", "tab:blue"), ("shock", "tab:orange")):
            selected = [r for r in records if r["model"] == model and r["scenario"] == scenario]
            curve = np.array([float(r["cost"]) for r in selected]).reshape(20,200,3).mean(axis=(0,2))
            axes[3].plot(periods, curve, label=f"{model}: {scenario}", color=color, linestyle=style)
    axes[3].set(title="Mean per-node cost", ylabel="Cost per node per period")
    for axis in axes:
        axis.axvspan(80.5,120.5,color="grey",alpha=0.15)
        axis.set(xlabel="Period (1-based)")
        axis.grid(alpha=0.25)
        axis.legend()
    fig.suptitle("Frozen HAPPO — 1.5x demand in periods 81–120, capped at 20")
    for extension in ("png","pdf"):
        fig.savefig(directory/f"demand_shock.{extension}",dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
