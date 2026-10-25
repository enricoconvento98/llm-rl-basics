"""Experiment: reward hacking in RLHF, and how the KL penalty limits it.

The "LLM" picks one of 20 answers, ordered from shortest (0) to longest (19).
The true quality is best for medium-short answers. The reward model (RM) has learned
a classic bias: it likes longer answers. We train with PPO against the RM using
reward = RM score - beta * log(pi / pi_ref), as in RLHF, and watch the true quality.
"""
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / "docs" / "results"
N = 20
length = np.arange(N) / (N - 1)                  # 0 = shortest answer, 1 = longest
true_quality = 1 - 6 * (length - 0.3) ** 2      # best around 30% length
rm_score = true_quality + 6 * length            # the RM over-rewards length
# The policy is a tiny 2-parameter "model": logits = theta1 * length + theta2 * length^2.
# Like a real LLM, nudging its parameters shifts probability smoothly between similar answers.
features = np.stack([length, length**2], axis=1)
ref_theta = np.array([10.0, -50.0])              # the SFT model writes short answers (~10% length)
ref_logits = features @ ref_theta


def softmax(x):
    e = np.exp(x - x.max())
    return e / e.sum()


LR = 2.0


def train_ppo(beta, iters=1000, batch=64, epochs=4, lr=LR, clip_eps=0.2, seed=0):
    rng = np.random.default_rng(seed)
    theta = ref_theta.copy()
    log_ref = np.log(softmax(ref_logits))
    hist = {"rm": [], "true": [], "kl": []}
    for _ in range(iters):
        pi_old = softmax(features @ theta)
        actions = rng.choice(N, size=batch, p=pi_old)
        # RLHF reward: RM score minus a per-sample KL penalty
        rewards = rm_score[actions] - beta * (np.log(pi_old[actions]) - log_ref[actions])
        adv = (rewards - rewards.mean()) / (rewards.std() + 1e-8)
        for _ in range(epochs):
            pi = softmax(features @ theta)
            ratio = pi[actions] / pi_old[actions]
            # gradient only flows where the clip is not active
            active = ~(((adv > 0) & (ratio > 1 + clip_eps)) | ((adv < 0) & (ratio < 1 - clip_eps)))
            # d/dtheta of ratio * A = ratio * A * (features[a] - E_pi[features]), summed over the batch
            w = ratio * adv * active
            grad = w @ (features[actions] - pi @ features)
            theta += lr * grad / batch
        pi = softmax(features @ theta)
        hist["rm"].append(pi @ rm_score)
        hist["true"].append(pi @ true_quality)
        hist["kl"].append(pi @ (np.log(pi) - log_ref))
    return hist, softmax(features @ theta)


betas = [0.0, 0.05, 0.2, 2.0]
results = {b: train_ppo(b) for b in betas}
ref_true = softmax(ref_logits) @ true_quality
print(f"reference model: true quality={ref_true:.2f}  (best possible {true_quality.max():.2f})")

fig, axes = plt.subplots(1, 3, figsize=(14, 3.6))
for b, (hist, _) in results.items():
    axes[0].plot(hist["rm"], label=f"β={b}")
    axes[1].plot(hist["true"], label=f"β={b}")
    axes[2].plot(hist["kl"], label=f"β={b}")
    print(f"beta={b:<5} RM reward={hist['rm'][-1]:.2f}  true quality={hist['true'][-1]:.2f}  KL={hist['kl'][-1]:.2f}")
axes[0].set(title="Reward-model score (what PPO optimizes)", xlabel="PPO iteration")
axes[1].axhline(ref_true, color="gray", linestyle="--", label="reference (SFT)")
axes[1].set(title="True quality (what we actually want)", xlabel="PPO iteration")
axes[2].set(title="KL(π ‖ π_ref)", xlabel="PPO iteration")
fig.legend(*axes[1].get_legend_handles_labels(), loc="lower center", ncol=5)
fig.tight_layout(rect=(0, 0.08, 1, 1))
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "reward_hacking.png", dpi=120)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 3.4))
ax1.plot(length, true_quality, "o-", label="true quality")
ax1.plot(length, rm_score, "o-", label="reward model score")
ax1.set(title="The reward model is biased toward length", xlabel="answer length")
ax1.legend()
ax2.plot(length, softmax(ref_logits), "k--", label="reference (SFT)")
for b, (_, pi) in results.items():
    ax2.plot(length, pi, "o-", markersize=3, label=f"after PPO, β={b}")
ax2.set(title="Final policy: which lengths it writes", xlabel="answer length", ylabel="probability")
ax2.legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "reward_hacking_policy.png", dpi=120)
