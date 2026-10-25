"""DPO with TRL on a small model and a preference dataset (chosen vs rejected answers)."""
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
