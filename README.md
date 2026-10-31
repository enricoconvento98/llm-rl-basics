# llm-rl-basics

Notes and small experiments for learning reinforcement learning for LLMs, following
[Hugging Face LLM Course – Chapter 12](https://huggingface.co/learn/llm-course/chapter12/2).

## Study plan

| Folder | Topic | Key ideas |
|---|---|---|
| `01-rl-basics` | RL fundamentals | agent, environment, state, action, reward, policy, return |
| `02-rlhf-ppo` | RLHF with PPO | reward model from human preferences, clipped policy updates, KL penalty against a reference model |
| `03-dpo` | Direct Preference Optimization | learns from chosen/rejected pairs directly, with no reward model and no RL loop |
| `04-grpo` | Group Relative Policy Optimization (DeepSeek-R1) | sample a group of answers per prompt, use the group's mean reward as the baseline, no value model |

Each folder has a `NOTES.md` for what you learn and a starter script you can run.

## RL trading system

[`rl-trading/`](rl-trading) is a separate project in this repo: a reinforcement learning trading
system (allocation + execution agents), built in validated stages. Start with
[`rl-trading/HANDOFF.md`](rl-trading/HANDOFF.md) and [`rl-trading/README.md`](rl-trading/README.md).

## Real experiments

- [`experiments/gsm8k_grpo`](experiments/gsm8k_grpo): GRPO on GSM8K math with Qwen2.5-0.5B in Colab
  ([open in Colab](https://colab.research.google.com/github/enricoconvento98/llm-rl-basics/blob/main/experiments/gsm8k_grpo/train_grpo_gsm8k.ipynb)).

## Docs and results

The site at **https://enricoconvento98.github.io/llm-rl-basics/** explains each topic and shows the charts.
It is built from `docs/` by `.github/workflows/docs.yml` on every push to `main`.

Preview it locally:

```bash
pip install -r requirements-docs.txt
./scripts/generate_results.sh
mkdocs serve
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

A GPU helps for `03-dpo` and `04-grpo`. Google Colab works fine.
