"""Experiment: REINFORCE with and without a baseline on a 10-armed bandit.

All rewards are positive (around +5), so without a baseline every action gets pushed up
and learning is slow and noisy. Subtracting a baseline fixes that.
"""
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / "docs" / "results"
N_ARMS, STEPS, SEEDS, LR = 10, 1000, 100, 0.05


def run(seed, use_baseline):
    rng = np.random.default_rng(seed)
    means = rng.normal(5.0, 1.0, N_ARMS)  # each arm's average reward
    best = means.argmax()
    logits = np.zeros(N_ARMS)
    baseline = 0.0
    rewards, optimal = np.zeros(STEPS), np.zeros(STEPS)
    for t in range(STEPS):
        probs = np.exp(logits - logits.max())
        probs /= probs.sum()
        a = rng.choice(N_ARMS, p=probs)
        r = rng.normal(means[a], 1.0)
        advantage = r - baseline if use_baseline else r
        grad = -probs
        grad[a] += 1
        logits += LR * advantage * grad
        baseline += 0.05 * (r - baseline)
        rewards[t] = r - means.max()  # regret-style: 0 means always picking the best arm
        optimal[t] = a == best
    return rewards, optimal


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.5))
for use_baseline, label in [(False, "no baseline"), (True, "with baseline")]:
    runs = [run(s, use_baseline) for s in range(SEEDS)]
    rewards = np.mean([r for r, _ in runs], axis=0)
    optimal = np.mean([o for _, o in runs], axis=0)
    print(f"{label:14s} final % optimal action: {optimal[-100:].mean():.0%}")
    ax1.plot(np.convolve(rewards, np.ones(20) / 20, "valid"), label=label)
    ax2.plot(np.convolve(optimal, np.ones(20) / 20, "valid"), label=label)
ax1.set(title="Reward minus best possible (higher is better)", xlabel="step")
ax2.set(title="% of steps picking the best arm", xlabel="step", ylim=(0, 1))
for ax in (ax1, ax2):
    ax.legend()
fig.suptitle(f"REINFORCE on a 10-armed bandit, averaged over {SEEDS} runs")
fig.tight_layout()
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "baseline_comparison.png", dpi=120)
