"""GRPO on GSM8K (grade-school math) with a small model, DeepSeek-R1 style.

Everything the notebook needs lives here, so the notebook stays short and the
parsing and reward logic can be tested on a laptop without a GPU.
Run end to end with:  python gsm8k_grpo.py --max-steps 200
"""
import argparse
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"

SYSTEM_PROMPT = (
    "Solve the math problem. First think step by step inside <think> </think> tags, "
    "then give only the final number inside <answer> </answer> tags."
)


@dataclass
class Config:
    model_id: str = "Qwen/Qwen2.5-0.5B-Instruct"
    train_size: int = 2000           # GSM8K training problems used for RL
    eval_size: int = 200             # held-out test problems, same set before and after
    max_steps: int = 200
    num_generations: int = 8         # the GRPO group size
    prompts_per_step: int = 2        # so each step samples prompts_per_step * num_generations answers
    max_completion_length: int = 256
    learning_rate: float = 2e-5      # LoRA needs a higher LR than full fine-tuning
    beta: float = 0.04               # KL penalty. TRL's default is 0.0, so we set it explicitly
    temperature: float = 0.9
    lora_r: int = 16
    lora_alpha: int = 32
    seed: int = 42


# ---------------------------------------------------------------- parsing

_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_ANSWER_TAG = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)
_FORMAT = re.compile(r"^\s*<think>.+?</think>\s*<answer>.+?</answer>\s*$", re.DOTALL)


def to_number(text):
    """Parse '1,234', '$12.50', '7.' and similar into a float, or None."""
    if text is None:
        return None
    match = _NUMBER.search(text.replace("$", ""))
    if not match:
        return None
    try:
        return float(match.group().replace(",", "").rstrip("."))
    except ValueError:
        return None


def gold_answer(solution):
    """GSM8K solutions end with '#### 72'."""
    return to_number(solution.split("####")[-1])


def extract_answer(completion):
    """The number in <answer> tags if present, else the last number in the text."""
    tagged = _ANSWER_TAG.findall(completion)
    if tagged:
        return to_number(tagged[-1])
    numbers = _NUMBER.findall(completion.replace("$", ""))
    return to_number(numbers[-1]) if numbers else None


def is_correct(completion, gold):
    pred = extract_answer(completion)
    return pred is not None and gold is not None and abs(pred - gold) < 1e-6


def has_format(completion):
    return bool(_FORMAT.match(completion))


# ---------------------------------------------------------------- rewards

def _text(completion):
    # TRL passes chat completions as [{"role": "assistant", "content": ...}]
    return completion[0]["content"] if isinstance(completion, list) else completion


def correctness_reward(completions, gold, **kwargs):
    """2.0 for the right final number, else 0. Only answers inside <answer> tags count."""
    rewards = []
    for completion, g in zip(completions, gold):
        tagged = _ANSWER_TAG.findall(_text(completion))
        rewards.append(2.0 if tagged and is_correct(tagged[-1], g) else 0.0)
    return rewards


def format_reward(completions, **kwargs):
    """0.5 for following <think>...</think><answer>...</answer> exactly."""
    return [0.5 if has_format(_text(c)) else 0.0 for c in completions]


# ---------------------------------------------------------------- data

def make_prompt(question):
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}]


def load_gsm8k(split, size, seed):
    from datasets import load_dataset

    ds = load_dataset("openai/gsm8k", "main", split=split).shuffle(seed=seed).select(range(size))
    return ds.map(lambda x: {"prompt": make_prompt(x["question"]), "gold": gold_answer(x["answer"])})


# ---------------------------------------------------------------- model, eval, training

def _bf16_ok():
    import torch

    return torch.cuda.is_available() and torch.cuda.is_bf16_supported()


def load_model(model_id):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")
    # T4 (free Colab) has no bf16: keep fp32 weights and train with fp16 autocast instead
    dtype = torch.bfloat16 if _bf16_ok() else torch.float32
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype).to(device)
    return model, tokenizer


def evaluate(model, tokenizer, dataset, max_new_tokens=256, batch_size=32):
    """Greedy answers on the eval set. Returns (metrics, per-problem outputs)."""
    import torch

    model.eval()
    model.config.use_cache = True
    outputs = []
    for start in range(0, len(dataset), batch_size):
        batch = dataset.select(range(start, min(start + batch_size, len(dataset))))
        texts = [tokenizer.apply_chat_template(p, tokenize=False, add_generation_prompt=True) for p in batch["prompt"]]
        inputs = tokenizer(texts, return_tensors="pt", padding=True).to(model.device)
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False,
                                       pad_token_id=tokenizer.pad_token_id)
        completions = tokenizer.batch_decode(generated[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        for question, gold, completion in zip(batch["question"], batch["gold"], completions):
            outputs.append({"question": question, "gold": gold, "completion": completion,
                            "correct": is_correct(completion, gold), "format": has_format(completion),
                            "tokens": len(tokenizer(completion)["input_ids"])})
        print(f"  evaluated {len(outputs)}/{len(dataset)}")
    n = len(outputs)
    metrics = {
        "accuracy": sum(o["correct"] for o in outputs) / n,
        "format_rate": sum(o["format"] for o in outputs) / n,
        "mean_tokens": sum(o["tokens"] for o in outputs) / n,
    }
    return metrics, outputs


def train(model, tokenizer, train_dataset, cfg):
    import torch
    from peft import LoraConfig
    from trl import GRPOConfig, GRPOTrainer

    bf16 = _bf16_ok()
    args = GRPOConfig(
        output_dir="outputs/gsm8k_grpo",
        max_steps=cfg.max_steps,
        per_device_train_batch_size=cfg.prompts_per_step * cfg.num_generations,
        num_generations=cfg.num_generations,
        max_completion_length=cfg.max_completion_length,
        learning_rate=cfg.learning_rate,
        beta=cfg.beta,
        temperature=cfg.temperature,
        bf16=bf16,
        fp16=torch.cuda.is_available() and not bf16,
        logging_steps=5,
        save_strategy="no",
        report_to="none",
        seed=cfg.seed,
    )
    peft_config = LoraConfig(r=cfg.lora_r, lora_alpha=cfg.lora_alpha, lora_dropout=0.05,
                             target_modules="all-linear", task_type="CAUSAL_LM")
    trainer = GRPOTrainer(model=model, processing_class=tokenizer, reward_funcs=[correctness_reward, format_reward],
                          args=args, train_dataset=train_dataset, peft_config=peft_config)
    start = time.time()
    trainer.train()
    return trainer, time.time() - start


# ---------------------------------------------------------------- results

def save_results(cfg, before, after, log_history, train_seconds, gpu_name, results_dir=RESULTS_DIR):
    """Write the small JSON files the docs site renders. Commit these, not the model."""
    (metrics_before, outputs_before), (metrics_after, outputs_after) = before, after
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "config.json").write_text(json.dumps(
        {**asdict(cfg), "gpu": gpu_name, "train_minutes": round(train_seconds / 60, 1)}, indent=1))
    (results_dir / "metrics.json").write_text(json.dumps({"before": metrics_before, "after": metrics_after}, indent=1))
    (results_dir / "train_log.json").write_text(json.dumps(log_history, indent=1))
    samples = [{"question": b["question"], "gold": b["gold"],
                "before": b["completion"], "before_correct": b["correct"],
                "after": a["completion"], "after_correct": a["correct"]}
               for b, a in zip(outputs_before, outputs_after)]
    (results_dir / "samples.json").write_text(json.dumps(samples, indent=1))
    print(f"Saved results to {results_dir}")


def main():
    import torch

    parser = argparse.ArgumentParser()
    for name, value in asdict(Config()).items():
        parser.add_argument("--" + name.replace("_", "-"), type=type(value), default=value)
    cfg = Config(**vars(parser.parse_args()))

    model, tokenizer = load_model(cfg.model_id)
    eval_ds = load_gsm8k("test", cfg.eval_size, cfg.seed)
    train_ds = load_gsm8k("train", cfg.train_size, cfg.seed)
    before = evaluate(model, tokenizer, eval_ds, cfg.max_completion_length)
    print("before:", before[0])
    trainer, seconds = train(model, tokenizer, train_ds, cfg)
    after = evaluate(trainer.model, tokenizer, eval_ds, cfg.max_completion_length)
    print("after:", after[0])
    gpu = torch.cuda.get_device_name() if torch.cuda.is_available() else "cpu"
    save_results(cfg, before, after, trainer.state.log_history, seconds, gpu)


if __name__ == "__main__":
    main()
