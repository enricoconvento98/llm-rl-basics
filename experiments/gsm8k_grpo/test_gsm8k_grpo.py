"""Run with: python -m pytest experiments/gsm8k_grpo  (no GPU needed)."""
import json

from gsm8k_grpo import (Config, correctness_reward, extract_answer, format_reward, gold_answer, has_format,
                        is_correct, save_results, to_number)

GOOD = "<think>48 / 2 = 24, and 48 + 24 = 72</think>\n<answer>72</answer>"


def test_to_number():
    assert to_number("1,234") == 1234
    assert to_number("$12.50") == 12.5
    assert to_number("7.") == 7
    assert to_number("-3") == -3
    assert to_number("no number") is None


def test_gold_answer():
    assert gold_answer("Natalia sold 48/2 = <<48/2=24>>24 clips.\n#### 72") == 72
    assert gold_answer("... #### 1,000") == 1000


def test_extract_answer_prefers_tag_then_last_number():
    assert extract_answer(GOOD) == 72
    assert extract_answer("So 3 + 4 = 7. The answer is 7.") == 7
    assert extract_answer("<answer>5</answer> but maybe 6") == 5
    assert extract_answer("I don't know") is None


def test_is_correct():
    assert is_correct(GOOD, 72.0)
    assert not is_correct(GOOD, 71.0)
    assert not is_correct("nothing", 72.0)


def test_has_format():
    assert has_format(GOOD)
    assert not has_format("<answer>72</answer>")
    assert not has_format("<think>x</think><answer>72</answer> extra text")


def test_rewards_accept_trl_chat_completions():
    completions = [[{"role": "assistant", "content": GOOD}],
                   [{"role": "assistant", "content": "The answer is 72"}],  # right number, but no tags
                   [{"role": "assistant", "content": "<think>x</think><answer>70</answer>"}]]
    gold = [72.0, 72.0, 72.0]
    # TRL also passes prompts, completion_ids, trainer_state and other columns as keyword arguments
    extra = {"prompts": [None] * 3, "completion_ids": [None] * 3, "trainer_state": None, "question": ["q"] * 3}
    assert correctness_reward(completions, gold=gold, **extra) == [2.0, 0.0, 0.0]
    assert format_reward(completions, gold=gold, **extra) == [0.5, 0.0, 0.5]


def test_rewards_accept_plain_strings():
    assert correctness_reward([GOOD], gold=[72.0]) == [2.0]
    assert format_reward([GOOD]) == [0.5]


def test_save_results(tmp_path):
    out = {"question": "q", "gold": 1.0, "completion": "c", "correct": True, "format": True, "tokens": 3}
    before = ({"accuracy": 0.3, "format_rate": 0.1, "mean_tokens": 100}, [out])
    after = ({"accuracy": 0.5, "format_rate": 0.9, "mean_tokens": 120}, [out])
    save_results(Config(), before, after, [{"step": 5, "reward": 0.4}], 600, "Tesla T4", tmp_path)
    assert json.loads((tmp_path / "metrics.json").read_text())["after"]["accuracy"] == 0.5
    assert json.loads((tmp_path / "config.json").read_text())["train_minutes"] == 10.0
    assert json.loads((tmp_path / "samples.json").read_text())[0]["after_correct"] is True
