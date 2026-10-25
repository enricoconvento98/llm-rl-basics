# GRPO on GSM8K

A real version of the toy GRPO experiment: Qwen2.5-0.5B-Instruct learns grade-school math with
verifiable rewards (right answer + right format), trained with LoRA on a free Colab T4.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/enricoconvento98/llm-rl-basics/blob/main/experiments/gsm8k_grpo/train_grpo_gsm8k.ipynb)

| File | What it is |
|---|---|
| `gsm8k_grpo.py` | Everything: answer parsing, reward functions, evaluation, training, saving results. Also runnable as a script: `python gsm8k_grpo.py --max-steps 200` |
| `train_grpo_gsm8k.ipynb` | Runs the module step by step in Colab and helps you commit the results |
| `test_gsm8k_grpo.py` | Tests for parsing and rewards, no GPU needed: `python -m pytest experiments/gsm8k_grpo` |
| `results/` | The four JSON files a run writes. Commit them and the docs site page updates itself |

Pinned to `trl==1.16.0` and `peft==0.21.2`.
