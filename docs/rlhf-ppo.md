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

## Experiment: reward hacking and the KL penalty

Source: [`02-rlhf-ppo/reward_hacking.py`](https://github.com/enricoconvento98/llm-rl-basics/blob/main/02-rlhf-ppo/reward_hacking.py).
The policy chooses how long an answer to write. The true quality is best for fairly short answers,
but the reward model has learned a common bias: **it likes longer answers**. We train with PPO
using the RLHF reward \(r = r_\text{RM} - \beta \log \frac{\pi}{\pi_\text{ref}}\) for several values of \(\beta\).

The policy is a tiny two-parameter model, \(\text{logits} = \theta_1 \cdot \text{length} + \theta_2 \cdot \text{length}^2\),
so, like a real LLM, a small parameter change shifts probability smoothly between similar answers.

![Reward hacking](results/reward_hacking.png)

![Reward hacking: policy](results/reward_hacking_policy.png)

| β | What happens |
|---|---|
| 0 | Climbs the reward model all the way to long answers. RM score is highest, true quality is **worse than before training**. |
| 0.05 | Still hacked, just less. |
| 0.2 | Moves to the length that is actually best. True quality goes from 0.76 to about 0.94. |
| 2 | Barely moves from the reference. Safe, but little improvement. |

!!! tip "Takeaway"
    The reward model is only a proxy. Pushing it too hard finds its mistakes (Goodhart's law).
    The KL penalty sets how far you trust it, and \(\beta\) is a real trade-off to tune.
