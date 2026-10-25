"""Experiment: GRPO on a toy math task, comparing group sizes.

Prompts are "a + b = ?" with a, b in 0..9. The policy is a softmax over answers 0..18
for each prompt. Reward is 1 if the answer is correct, else 0 (a verifiable reward,
like DeepSeek-R1). When every answer in a group gets the same reward, all advantages
are 0 and the prompt teaches nothing, which is why the group size matters so much.
"""
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[1] / "docs" / "results"
PROMPTS = [(a, b) for a in range(10) for b in range(10)]
N_ANSWERS = 19
STEPS, PROMPTS_PER_STEP, LR = 300, 16, 1.0


def softmax(x):
    e = np.exp(x - x.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def train_grpo(group_size, seed=0):
    rng = np.random.default_rng(seed)
    logits = np.zeros((len(PROMPTS), N_ANSWERS))  # starts as a uniform guess: 1/19 chance correct
    acc, dead, samples = [], [], []
    total = 0
    for _ in range(STEPS):
        batch = rng.choice(len(PROMPTS), PROMPTS_PER_STEP, replace=False)
        grad = np.zeros_like(logits)
        n_dead = 0
        for p in batch:
            a, b = PROMPTS[p]
            pi = softmax(logits[p])
            answers = rng.choice(N_ANSWERS, size=group_size, p=pi)
            rewards = (answers == a + b).astype(float)
            if rewards.std() == 0:
                n_dead += 1                       # all same reward -> zero advantage -> no learning
                continue
            adv = (rewards - rewards.mean()) / rewards.std()
            for y, A in zip(answers, adv):
                g = -pi * A
                g[y] += A
                grad[p] += g / group_size
        logits += LR * grad
        total += PROMPTS_PER_STEP * group_size
        probs = softmax(logits)
        acc.append(np.mean([probs[i, a + b] for i, (a, b) in enumerate(PROMPTS)]))
        dead.append(n_dead / PROMPTS_PER_STEP)
        samples.append(total)
    return acc, dead, samples


fig, axes = plt.subplots(1, 3, figsize=(14, 3.6))
for G in [2, 4, 8, 16, 32]:
    acc, dead, samples = train_grpo(G)
    print(f"G={G:<3} final accuracy={acc[-1]:.0%}  groups with no signal (last 50 steps)={np.mean(dead[-50:]):.0%}")
    axes[0].plot(acc, label=f"G={G}")
    axes[1].plot(samples, acc, label=f"G={G}")
    axes[2].plot(np.convolve(dead, np.ones(10) / 10, "valid"), label=f"G={G}")
axes[0].set(title="Accuracy vs training step", xlabel="step", ylabel="P(correct answer)")
axes[1].set(title="Accuracy vs answers generated (compute)", xlabel="completions sampled", xscale="log")
axes[2].set(title="Groups with zero advantage (wasted)", xlabel="step", ylim=(0, 1.05))
for ax in axes:
    ax.legend()
fig.tight_layout()
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "grpo_group_size.png", dpi=120)
