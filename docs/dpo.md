# 3. DPO

**Direct Preference Optimization** gets RLHF's effect without a reward model or an RL loop.
It trains on pairs of a chosen answer \(y_w\) and a rejected answer \(y_l\):

\[
L_\text{DPO} = -\log \sigma\Big(\beta \log \frac{\pi_\theta(y_w \mid x)}{\pi_\text{ref}(y_w \mid x)}
- \beta \log \frac{\pi_\theta(y_l \mid x)}{\pi_\text{ref}(y_l \mid x)}\Big)
\]

It raises the chosen answer's likelihood relative to a frozen reference model and lowers the rejected one's.
\(\beta\) controls how far the model may move from the reference.

## Result

Source: [`03-dpo/train_dpo.py`](https://github.com/enricoconvento98/llm-rl-basics/blob/main/03-dpo/train_dpo.py)
(needs a GPU). Watch `rewards/accuracies`: how often the model now prefers the chosen answer.

![DPO training](results/dpo.png)
