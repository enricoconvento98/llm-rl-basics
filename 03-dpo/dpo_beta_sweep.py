"""Experiment: DPO from scratch on a toy problem, sweeping beta.

One prompt, 10 possible answers with a hidden true quality. Annotators compare pairs
and prefer the better answer most of the time (Bradley-Terry model, so labels are noisy).
We train a policy with the DPO loss and see how beta trades off fitting the
preferences against staying close to the reference model.
"""
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / "docs" / "results"
N = 10
rng = np.random.default_rng(0)
quality = np.linspace(2, -2, N)                  # answer 0 is best
ref_logits = rng.normal(0, 1, N)                 # reference model: no idea which is best


def softmax(x):
    e = np.exp(x - x.max())
    return e / e.sum()


# Preference dataset: (chosen, rejected) pairs labelled by noisy annotators
pairs = []
for _ in range(500):
    i, j = rng.choice(N, 2, replace=False)
    p_i = 1 / (1 + np.exp(-(quality[i] - quality[j])))
    pairs.append((i, j) if rng.random() < p_i else (j, i))
pairs = np.array(pairs)
train, test = pairs[:400], pairs[400:]


def train_dpo(beta, epochs=500, lr=2.0):
    theta = ref_logits.copy()
    hist = {"loss": [], "acc": [], "kl": [], "best": []}
    for _ in range(epochs):
        # log pi(y) - log pi_ref(y) = (theta - ref)[y] + const, and the const cancels in the margin
        delta = theta - ref_logits
        margin = beta * (delta[train[:, 0]] - delta[train[:, 1]])
        weight = 1 / (1 + np.exp(margin))        # = 1 - sigmoid(margin)
        grad = np.zeros(N)
        np.add.at(grad, train[:, 0], -beta * weight)
        np.add.at(grad, train[:, 1], beta * weight)
        # lr / beta**2 makes the margin (beta * delta) move at the same speed for every beta,
        # so each run converges and we compare where it ends up, not how fast it gets there
        theta -= lr / beta**2 * grad / len(train)
        test_delta = theta - ref_logits
        hist["loss"].append(np.mean(np.log1p(np.exp(-margin))))
        hist["acc"].append(np.mean(test_delta[test[:, 0]] > test_delta[test[:, 1]]))
        pi, pi_ref = softmax(theta), softmax(ref_logits)
        hist["kl"].append(pi @ (np.log(pi) - np.log(pi_ref)))
        hist["best"].append(pi[0])
    return hist, softmax(theta)


betas = [0.1, 0.3, 1.0, 3.0]
results = {b: train_dpo(b) for b in betas}

fig, axes = plt.subplots(1, 3, figsize=(14, 3.8))
for b, (hist, pi) in results.items():
    axes[0].plot(hist["loss"], label=f"β={b}")
    axes[1].plot(hist["kl"], label=f"β={b}")
    axes[2].plot(hist["best"], label=f"β={b}")
    print(f"beta={b:<5} test pref. accuracy={hist['acc'][-1]:.0%}  KL={hist['kl'][-1]:.2f}  P(best answer)={pi[0]:.2f}")
axes[0].set(title="DPO loss (same for every β)", xlabel="epoch")
axes[1].set(title="KL(π ‖ π_ref): how far the model moved", xlabel="epoch")
axes[2].set(title="P(best answer)", xlabel="epoch", ylim=(0, 1))
fig.legend(*axes[1].get_legend_handles_labels(), loc="lower center", ncol=4)
fig.tight_layout(rect=(0, 0.08, 1, 1))
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "dpo_beta_sweep.png", dpi=120)

fig, ax = plt.subplots(figsize=(10, 3.2))
x = np.arange(N)
width = 0.8 / (len(betas) + 1)
ax.bar(x - 0.4 + width / 2, softmax(ref_logits), width, label="reference", color="gray")
for i, (b, (_, pi)) in enumerate(results.items(), start=1):
    ax.bar(x - 0.4 + width / 2 + i * width, pi, width, label=f"DPO β={b}")
ax.set(title="Final policy over answers (answer 0 is best, 9 is worst)", xlabel="answer", ylabel="probability", xticks=x)
ax.legend(ncol=5, fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "dpo_policy.png", dpi=120)
