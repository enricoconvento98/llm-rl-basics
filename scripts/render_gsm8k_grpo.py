"""Build docs/real-gsm8k-grpo.md and its chart from experiments/gsm8k_grpo/results/*.json.

The page is generated (and git-ignored), so committing new results is all it takes to update the site.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RESULTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "experiments" / "gsm8k_grpo" / "results"
PAGE = ROOT / "docs" / "real-gsm8k-grpo.md"
CHART = ROOT / "docs" / "results" / "gsm8k_grpo_training.png"
REPO = "https://github.com/enricoconvento98/llm-rl-basics/blob/main"
NOTEBOOK = "experiments/gsm8k_grpo/train_grpo_gsm8k.ipynb"
COLAB = f"https://colab.research.google.com/github/enricoconvento98/llm-rl-basics/blob/main/{NOTEBOOK}"

INTRO = f"""# Real experiment: GRPO on GSM8K

This is the toy GRPO experiment for real: a small instruction-tuned LLM
learns grade-school math with **verifiable rewards** and no reward model, like DeepSeek-R1.

- **Model:** Qwen2.5-0.5B-Instruct, trained with LoRA so it fits on a free Colab T4 GPU.
- **Data:** [GSM8K](https://huggingface.co/datasets/openai/gsm8k) word problems.
- **Rewards:** `correctness_reward` (2.0 if the number in `<answer>` tags is right) and
  `format_reward` (0.5 for `<think>…</think><answer>…</answer>`).
- **Evaluation:** greedy answers on the same held-out test problems before and after training.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)]({COLAB})
&nbsp; Code: [`gsm8k_grpo.py`]({REPO}/experiments/gsm8k_grpo/gsm8k_grpo.py),
[notebook]({REPO}/{NOTEBOOK})
"""

NOT_RUN = """
!!! warning "Not run yet"
    Open the notebook in Colab (Runtime → Change runtime type → T4 GPU), run all cells
    (about 1-2 hours), then commit the files it writes to `experiments/gsm8k_grpo/results/`.
    This page then fills in with the before/after scores, training curves and example answers.
"""


def series(log, *keys):
    for key in keys:
        points = [(e["step"], e[key]) for e in log if key in e]
        if points:
            return list(zip(*points))
    return None


def plot(log):
    panels = [
        ("Reward per answer", [("correctness (max 2)", "rewards/correctness_reward/mean"),
                               ("format (max 0.5)", "rewards/format_reward/mean")]),
        ("Groups with no learning signal", [("all answers same reward", "frac_reward_zero_std")]),
        ("Answer length (tokens)", [("mean", "completions/mean_length")]),
        ("KL to the starting model", [("kl", "kl")]),
    ]
    fig, axes = plt.subplots(1, 4, figsize=(17, 3.6))
    for ax, (title, lines) in zip(axes, panels):
        for label, key in lines:
            data = series(log, key)
            if data:
                ax.plot(*data, label=label)
        ax.set(title=title, xlabel="step")
        if len(lines) > 1:
            ax.legend(fontsize=8)
    clipped = series(log, "completions/clipped_ratio")
    if clipped:
        twin = axes[2].twinx()
        twin.plot(*clipped, color="gray", linestyle=":", label="hit the length limit")
        twin.set_ylim(0, 1)
        twin.set_ylabel("fraction hitting the limit", color="gray")
    axes[1].set_ylim(0, 1)
    fig.tight_layout()
    CHART.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART, dpi=120)


def answer_block(title, text, kind):
    body = "\n".join("        " + line for line in text.strip().splitlines()) or "        (empty)"
    return f'    ??? {kind} "{title}"\n        ```text\n{body}\n        ```\n'


def examples(samples, n=3):
    fixed = [s for s in samples if s["after_correct"] and not s["before_correct"]]
    broken = [s for s in samples if s["before_correct"] and not s["after_correct"]]
    still_wrong = [s for s in samples if not s["after_correct"] and not s["before_correct"]]
    out = []
    for heading, group, count in [("Fixed by training", fixed, n), ("Broken by training", broken, 1),
                                  ("Still wrong", still_wrong, 1)]:
        if not group:
            continue
        out.append(f"### {heading} ({len(group)} of {len(samples)} problems)\n")
        for s in group[:count]:
            gold = int(s["gold"]) if float(s["gold"]).is_integer() else s["gold"]
            out.append(f"!!! question \"{s['question']}\"\n    Correct answer: **{gold}**\n")
            out.append(answer_block("Before training " + ("✅" if s["before_correct"] else "❌"), s["before"],
                                    "success" if s["before_correct"] else "failure"))
            out.append(answer_block("After training " + ("✅" if s["after_correct"] else "❌"), s["after"],
                                    "success" if s["after_correct"] else "failure"))
    return "\n".join(out)


def main():
    files = {name: RESULTS / f"{name}.json" for name in ["config", "metrics", "train_log", "samples"]}
    if not all(f.exists() for f in files.values()):
        PAGE.write_text(INTRO + NOT_RUN)
        print(f"No results in {RESULTS}: wrote placeholder page")
        return
    cfg, metrics, log, samples = (json.loads(f.read_text()) for f in files.values())
    plot(log)
    b, a = metrics["before"], metrics["after"]
    rows = [("Accuracy", "accuracy", "{:.1%}"), ("Follows the format", "format_rate", "{:.1%}"),
            ("Mean answer length (tokens)", "mean_tokens", "{:.0f}")]
    table = "| Metric | Before | After |\n|---|---|---|\n" + "\n".join(
        f"| {label} | {fmt.format(b[k])} | **{fmt.format(a[k])}** |" for label, k, fmt in rows)
    config_rows = "\n".join(f"| `{k}` | {v} |" for k, v in cfg.items())
    page = f"""{INTRO}
## Results

Evaluated on {cfg['eval_size']} held-out GSM8K test problems (greedy decoding).

{table}

## Training curves

![GRPO on GSM8K training curves](results/gsm8k_grpo_training.png)

- **Reward:** the format reward usually rises first (it's easy), then correctness follows.
- **Groups with no learning signal:** a group where every answer gets the same reward teaches nothing.
  Compare with the [toy group-size experiment](grpo.md#experiment-group-size-on-a-toy-math-task).
- **KL:** how far the policy has moved from the starting model, controlled by `beta`.

## Example answers

{examples(samples)}

## Configuration

| Setting | Value |
|---|---|
{config_rows}
"""
    PAGE.write_text(page)
    print(f"Wrote {PAGE.relative_to(ROOT)} and {CHART.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
