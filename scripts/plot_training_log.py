"""Plot a TRL trainer log (docs/results/<name>_log.json) to docs/results/<name>.png.

If the log doesn't exist yet, draws a placeholder so the docs page still renders.
Usage: python scripts/plot_training_log.py dpo loss rewards/accuracies
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / "docs" / "results"

name, *metrics = sys.argv[1:]
log_file = OUT / f"{name}_log.json"
fig, axes = plt.subplots(1, len(metrics), figsize=(5 * len(metrics), 3.5), squeeze=False)

if log_file.exists():
    log = json.loads(log_file.read_text())
    for ax, metric in zip(axes[0], metrics):
        points = [(e["step"], e[metric]) for e in log if metric in e]
        ax.plot(*zip(*points)) if points else ax.text(0.5, 0.5, "not logged", ha="center")
        ax.set(title=metric, xlabel="step")
else:
    for ax in axes[0]:
        ax.set_axis_off()
    fig.text(0.5, 0.45, f"No results yet.\nRun the training script and commit docs/results/{name}_log.json",
             ha="center", va="center", fontsize=12)

fig.suptitle(f"{name.upper()} training")
fig.tight_layout()
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / f"{name}.png", dpi=120)
