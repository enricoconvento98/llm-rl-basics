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

## Result: training with TRL (GPU)

Source: [`04-grpo/train_grpo.py`](https://github.com/enricoconvento98/llm-rl-basics/blob/main/04-grpo/train_grpo.py)
(needs a GPU). The toy reward favors completions of about 50 characters, so `reward` should rise toward 0.

![GRPO training](results/grpo.png)

## Experiment: group size on a toy math task

Source: [`04-grpo/grpo_group_size.py`](https://github.com/enricoconvento98/llm-rl-basics/blob/main/04-grpo/grpo_group_size.py).
Prompts are "a + b = ?" for digits a and b. The model starts by guessing uniformly over 0-18
(a 1-in-19 chance of being right) and gets reward 1 only for the correct answer: a **verifiable
reward**, like DeepSeek-R1's math training.

![GRPO group size](results/grpo_group_size.png)

- **Left:** bigger groups learn in fewer steps. With G=2, both answers are usually wrong, so most prompts give no signal.
- **Middle:** per answer generated, though, small groups are more efficient. Larger groups cost more compute per step.
- **Right:** a group where every answer gets the same reward has zero advantage everywhere and teaches nothing.
  Early on that happens because *all answers are wrong*, and late in training because *all answers are right*.

!!! tip "Takeaway"
    GRPO only learns from prompts where the answers *disagree*. Pick tasks that are hard but not
    impossible for the current model, and a group size big enough that some answers succeed.
