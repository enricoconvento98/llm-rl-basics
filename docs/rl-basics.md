# 1. RL basics

An **agent** acts in an **environment**. At each step it sees a **state** \(s\), picks an
**action** \(a\) from its **policy** \(\pi(a \mid s)\), and gets a **reward** \(r\).
The goal is to find the policy that maximizes the expected total reward.

For an LLM: the state is the prompt plus the text written so far, an action is the next token,
and the reward usually comes once the full answer is done.

## Policy gradient (REINFORCE)

Push up the probability of actions that did better than expected:

\[
\nabla_\theta J = \mathbb{E}\big[(r - b)\, \nabla_\theta \log \pi_\theta(a)\big]
\]

\(b\) is a **baseline** (here a running average of the reward). Subtracting it doesn't change the
direction on average, but it makes the updates much less noisy.

## Result: a 3-armed bandit

Source: [`01-rl-basics/bandit.py`](https://github.com/enricoconvento98/llm-rl-basics/blob/main/01-rl-basics/bandit.py).
Three slot machines pay out with probability 0.2, 0.5 and 0.8. The policy starts uniform and
learns to pick the best one.

![Bandit training](results/bandit.png)

## Experiment: why the baseline matters

Source: [`01-rl-basics/baseline_comparison.py`](https://github.com/enricoconvento98/llm-rl-basics/blob/main/01-rl-basics/baseline_comparison.py).
A 10-armed bandit where every reward is around +5. Without a baseline, every action that gets
picked is pushed **up**, just by different amounts, so the signal is buried in noise. With a
baseline, only better-than-average actions are pushed up. Averaged over 100 runs:

![Baseline comparison](results/baseline_comparison.png)

!!! tip "Takeaway"
    Policy gradient learns from **how much better than expected** an action was, not from the
    raw reward. The baseline becomes the *value model* in PPO and the *group mean* in GRPO.
