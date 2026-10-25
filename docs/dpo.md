# 3. DPO

**Direct Preference Optimization** gets RLHF's effect without a reward model or an RL loop.
It trains on pairs of a chosen answer \(y_w\) and a rejected answer \(y_l\):

\[
L_\text{DPO} = -\log \sigma\Big(\beta \log \frac{\pi_\theta(y_w \mid x)}{\pi_\text{ref}(y_w \mid x)}
- \beta \log \frac{\pi_\theta(y_l \mid x)}{\pi_\text{ref}(y_l \mid x)}\Big)
\]

It raises the chosen answer's likelihood relative to a frozen reference model and lowers the rejected one's.
\(\beta\) controls how far the model may move from the reference.

## Result: training with TRL (GPU)

Source: [`03-dpo/train_dpo.py`](https://github.com/enricoconvento98/llm-rl-basics/blob/main/03-dpo/train_dpo.py)
(needs a GPU). Watch `rewards/accuracies`: how often the model now prefers the chosen answer.

![DPO training](results/dpo.png)

## Experiment: what β does in DPO

Source: [`03-dpo/dpo_beta_sweep.py`](https://github.com/enricoconvento98/llm-rl-basics/blob/main/03-dpo/dpo_beta_sweep.py).
DPO from scratch, in NumPy: one prompt with 10 possible answers, and 400 preference pairs from
annotators who pick the better answer most of the time (the labels are noisy). The reference
model starts with no idea which answer is best.

![DPO beta sweep](results/dpo_beta_sweep.png)

![DPO final policies](results/dpo_policy.png)

The loss curve is the **same for every β**, and so is held-out preference accuracy (79%):
β doesn't change *which* preferences the model learns, only **how far it moves** to express them.
The optimal policy is \(\pi \propto \pi_\text{ref} \cdot e^{r/\beta}\), so a small β turns the same learned
preferences into a much sharper policy. At β=0.1 it puts all its probability on the best answer.

!!! tip "Takeaway"
    Small β fits the preferences hard and drifts far from the reference. That's great with clean data,
    and risky with noisy data or when you need to keep the model's other skills. Large β stays close.
