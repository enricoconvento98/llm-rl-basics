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
