#!/usr/bin/env bash
# Regenerate every chart shown on the docs site.
set -euo pipefail
cd "$(dirname "$0")/.."
python 01-rl-basics/bandit.py
python 01-rl-basics/baseline_comparison.py
python 02-rlhf-ppo/ppo_clip.py
python 02-rlhf-ppo/reward_hacking.py
python 03-dpo/dpo_beta_sweep.py
python 04-grpo/group_advantage.py
python 04-grpo/grpo_group_size.py
python scripts/plot_training_log.py dpo loss rewards/accuracies rewards/margins
python scripts/plot_training_log.py grpo loss reward
python scripts/render_gsm8k_grpo.py
