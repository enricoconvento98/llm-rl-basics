"""The PPO clipped objective, written out so you can play with the numbers."""
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / "docs" / "results"


def ppo_objective(ratio, advantage, clip_eps=0.2):
    """What PPO maximizes for one action; the loss is the negative of this."""
    return np.minimum(ratio * advantage, np.clip(ratio, 1 - clip_eps, 1 + clip_eps) * advantage)


if __name__ == "__main__":
    p_old = np.array([0.30, 0.50, 0.20])
    p_new = np.array([0.45, 0.40, 0.15])
    adv = np.array([1.0, -0.5, 0.2])
    ratio = p_new / p_old
    print("ratio:", np.round(ratio, 3))
    print("loss :", round(-ppo_objective(ratio, adv).mean(), 4))

    r = np.linspace(0, 2, 400)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5), sharey=False)
    for ax, a in zip(axes, [1.0, -1.0]):
        ax.plot(r, r * a, "--", color="gray", label="unclipped  r·A")
        ax.plot(r, ppo_objective(r, a), linewidth=2, label="PPO clipped objective")
        ax.axvspan(0.8, 1.2, alpha=0.1, label="trust region 1±ε")
        ax.set(title=f"Advantage A = {a:+.0f}", xlabel="ratio r = π_new / π_old", ylabel="objective")
        ax.legend()
    fig.tight_layout()
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "ppo_clip.png", dpi=120)
