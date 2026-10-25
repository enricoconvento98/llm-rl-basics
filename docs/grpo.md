# 4. GRPO

**Group Relative Policy Optimization** is the method used to train DeepSeek-R1.
For each prompt it samples a **group** of \(G\) answers, scores each with a reward function,
and uses the group itself as the baseline:

\[
A_i = \frac{r_i - \text{mean}(r_1, \dots, r_G)}{\text{std}(r_1, \dots, r_G)}
\]

Then it applies a PPO-style clipped update with a KL penalty. Because the baseline comes from the group,
there is **no value model** to train, which saves a lot of memory. Rewards can be simple rules,
such as "is the final answer correct?" or "is the output in the right format?".

## Result: group-relative advantages

Source: [`04-grpo/group_advantage.py`](https://github.com/enricoconvento98/llm-rl-basics/blob/main/04-grpo/group_advantage.py).
Answers better than the group average get a positive advantage; worse ones get a negative one.

![GRPO advantages](results/grpo_advantage.png)

## Result: training

Source: [`04-grpo/train_grpo.py`](https://github.com/enricoconvento98/llm-rl-basics/blob/main/04-grpo/train_grpo.py)
(needs a GPU). The toy reward favors completions of about 50 characters, so `reward` should rise toward 0.

![GRPO training](results/grpo.png)
