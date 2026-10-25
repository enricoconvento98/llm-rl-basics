"""Policy gradient (REINFORCE) on a 3-armed bandit: the smallest RL loop."""
import numpy as np

rng = np.random.default_rng(0)
true_rewards = np.array([0.2, 0.5, 0.8])  # expected reward of each arm
logits = np.zeros(3)                       # the policy's parameters
lr = 0.1
baseline = 0.0

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

    if step % 500 == 0:
        print(f"step {step:4d}  probs={np.round(probs, 3)}")

print("final policy:", np.round(np.exp(logits) / np.exp(logits).sum(), 3))
