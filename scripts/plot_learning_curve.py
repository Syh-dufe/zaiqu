"""Render exported training/evaluation curves; requires matplotlib."""
import argparse
import csv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    options = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = list(csv.DictReader((options.directory / "curve.csv").open(encoding="utf-8")))
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for ax, phase in zip(axes, ("training", "evaluation")):
        selected = [row for row in rows if row["phase"] == phase]
        ax.plot([int(row["step"]) for row in selected],
                [float(row["mean_actor_period_cost"]) for row in selected],
                marker="o" if phase == "evaluation" else None, linewidth=1.5)
        ax.set(title=phase.title(), xlabel="Environment transitions",
               ylabel="Mean cost per agent per period (lower is better)")
        ax.grid(alpha=0.25)
    fig.suptitle("Official Liu rules — seed 11 — 50,000 transitions")
    for extension in ("png", "pdf"):
        fig.savefig(options.directory / f"learning_curve.{extension}", dpi=180)
    plt.close(fig)
    print(options.directory / "learning_curve.png")


if __name__ == "__main__":
    main()
