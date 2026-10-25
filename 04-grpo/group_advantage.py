"""How GRPO turns a group of rewards into advantages (no value model needed)."""
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / "docs" / "results"

rewards = np.array([1.0, 0.0, 0.0, 1.0, 0.5])  # rewards for 5 answers to the same prompt
advantages = (rewards - rewards.mean()) / (rewards.std() + 1e-8)
for r, a in zip(rewards, advantages):
    print(f"reward={r:.1f}  advantage={a:+.2f}")

x = np.arange(len(rewards))
fig, ax = plt.subplots(figsize=(7, 3.5))
ax.bar(x - 0.2, rewards, width=0.4, label="reward")
ax.bar(x + 0.2, advantages, width=0.4, label="advantage (normalized in group)")
ax.axhline(0, color="black", linewidth=0.8)
ax.set(xticks=x, xticklabels=[f"answer {i + 1}" for i in x], title="GRPO: rewards → group-relative advantages")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
fig.tight_layout()
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "grpo_advantage.png", dpi=120)
