"""Policy gradient (REINFORCE) on a 3-armed bandit: the smallest RL loop."""
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / "docs" / "results"

rng = np.random.default_rng(0)
true_rewards = np.array([0.2, 0.5, 0.8])  # expected reward of each arm
logits = np.zeros(3)                       # the policy's parameters
lr = 0.1
baseline = 0.0
history, rewards = [], []

for step in range(2000):
    probs = np.exp(logits) / np.exp(logits).sum()
    action = rng.choice(3, p=probs)
    reward = float(rng.random() < true_rewards[action])

    # REINFORCE: grad of log pi(a) = onehot(a) - probs
    advantage = reward - baseline
    grad = -probs
    grad[action] += 1
    logits += lr * advantage * grad
    baseline = 0.99 * baseline + 0.01 * reward

    history.append(probs)
    rewards.append(reward)
    if step % 500 == 0:
        print(f"step {step:4d}  probs={np.round(probs, 3)}")

print("final policy:", np.round(np.exp(logits) / np.exp(logits).sum(), 3))

history = np.array(history)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.5))
for arm in range(3):
    ax1.plot(history[:, arm], label=f"arm {arm} (p win={true_rewards[arm]})")
ax1.set(title="Policy: probability of each arm", xlabel="step", ylabel="probability")
ax1.legend()
window = 50
ax2.plot(np.convolve(rewards, np.ones(window) / window, mode="valid"))
ax2.axhline(true_rewards.max(), color="gray", linestyle="--", label="best possible")
ax2.set(title=f"Reward ({window}-step moving average)", xlabel="step", ylabel="reward")
ax2.legend()
fig.tight_layout()
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "bandit.png", dpi=120)
