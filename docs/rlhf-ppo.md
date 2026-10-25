# 2. RLHF & PPO

**RLHF** (reinforcement learning from human feedback) has three stages:

1. **Supervised fine-tuning:** teach the model to follow instructions.
2. **Reward model:** people compare pairs of answers, and a model learns to score answers the way they would.
3. **RL with PPO:** the LLM generates answers, the reward model scores them, and PPO updates the LLM.
   A KL penalty keeps it close to the original model so it doesn't drift into nonsense that fools the reward model.

## The PPO clipped objective

With the probability ratio \(r = \pi_\text{new}(a) / \pi_\text{old}(a)\) and advantage \(A\):

\[
L^\text{CLIP} = \mathbb{E}\Big[\min\big(r A,\ \text{clip}(r, 1-\varepsilon, 1+\varepsilon)\, A\big)\Big]
\]

Once the ratio leaves \([1-\varepsilon, 1+\varepsilon]\) in the direction that would help, the objective
goes flat, so there is no gradient pushing further. That keeps each update small.

## Result

Source: [`02-rlhf-ppo/ppo_clip.py`](https://github.com/enricoconvento98/llm-rl-basics/blob/main/02-rlhf-ppo/ppo_clip.py).

![PPO clipped objective](results/ppo_clip.png)
