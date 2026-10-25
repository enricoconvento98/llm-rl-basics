# LLM RL Basics

My notes and experiments while learning reinforcement learning for LLMs, following
[Hugging Face LLM Course, Chapter 12](https://huggingface.co/learn/llm-course/chapter12/2).

| Step | Topic | Idea in one line |
|---|---|---|
| [1](rl-basics.md) | RL basics | An agent learns a policy that maximizes reward through trial and error. |
| [2](rlhf-ppo.md) | RLHF & PPO | Train a reward model on human preferences, then optimize the LLM against it with small, clipped steps. |
| [3](dpo.md) | DPO | Skip the reward model: learn directly from chosen vs rejected answers. |
| [4](grpo.md) | GRPO | Sample a group of answers per prompt and score each one against the group's average. |

!!! info "How the results get here"
    Every push to `main` re-runs the CPU demos and redraws the charts.
    DPO and GRPO need a GPU: run them yourself (Colab works), commit the
    `docs/results/*_log.json` file they write, and their charts update.
