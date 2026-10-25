"""DPO with TRL on a small model and a preference dataset (chosen vs rejected answers)."""
import json
from pathlib import Path

from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOConfig, DPOTrainer

model_id = "Qwen/Qwen2.5-0.5B-Instruct"
model = AutoModelForCausalLM.from_pretrained(model_id)
tokenizer = AutoTokenizer.from_pretrained(model_id)

dataset = load_dataset("trl-lib/ultrafeedback_binarized", split="train[:1000]")

args = DPOConfig(output_dir="outputs/dpo", beta=0.1, per_device_train_batch_size=2, max_steps=100, logging_steps=10)
trainer = DPOTrainer(model=model, args=args, train_dataset=dataset, processing_class=tokenizer)
trainer.train()

# Save the metrics so the docs site can plot them (commit this file).
out = Path(__file__).resolve().parents[1] / "docs" / "results" / "dpo_log.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(trainer.state.log_history, indent=1))
