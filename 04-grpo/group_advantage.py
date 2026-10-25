"""How GRPO turns a group of rewards into advantages (no value model needed)."""
import numpy as np

rewards = np.array([1.0, 0.0, 0.0, 1.0, 0.5])  # rewards for 5 answers to the same prompt
advantages = (rewards - rewards.mean()) / (rewards.std() + 1e-8)
for r, a in zip(rewards, advantages):
    print(f"reward={r:.1f}  advantage={a:+.2f}")
