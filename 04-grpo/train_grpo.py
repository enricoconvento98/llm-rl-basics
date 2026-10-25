"""GRPO with TRL: reward short completions (a toy reward, like in the HF course)."""
from datasets import load_dataset
from trl import GRPOConfig, GRPOTrainer

dataset = load_dataset("trl-lib/tldr", split="train[:1000]")


def reward_len(completions, **kwargs):
    # Higher reward the closer the completion is to 50 characters.
    return [-abs(50 - len(c)) for c in completions]


args = GRPOConfig(
    output_dir="outputs/grpo",
    num_generations=4,          # group size: completions sampled per prompt
    per_device_train_batch_size=4,
    max_completion_length=64,
    max_steps=100,
    logging_steps=10,
)
trainer = GRPOTrainer(
    model="Qwen/Qwen2.5-0.5B-Instruct",
    reward_funcs=reward_len,
    args=args,
    train_dataset=dataset,
)
trainer.train()
