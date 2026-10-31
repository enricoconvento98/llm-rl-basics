import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rltrading.config import FeaturesConfig, MomentumConfig
from rltrading.features import build_features, warmup_sessions
from rltrading.features.core import (
    average_correlation,
    log_returns,
    momentum,
    pairwise_correlation,
    volatility,
)

CFG = FeaturesConfig(
    return_windows=[1, 5],
    volatility_windows=[5],
    correlation_window=6,
    momentum=MomentumConfig(lookback=10, skip=2),
    sessions_per_year=252,
)


def random_prices(n: int, assets: int = 3, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01 21:00", periods=n, freq="B", tz="UTC")
    rets = rng.normal(0, 0.01, (n, assets))
    return pd.DataFrame(
        100 * np.exp(rets.cumsum(axis=0)), index=idx, columns=[f"a{i}" for i in range(assets)]
    )


def test_log_returns_and_momentum_values() -> None:
    p = pd.DataFrame({"x": [100.0, 110.0, 121.0, 133.1]})
    assert log_returns(p, 1)["x"].iloc[1] == pytest.approx(np.log(1.1))
    assert log_returns(p, 2)["x"].iloc[3] == pytest.approx(np.log(1.21))
    assert momentum(p, lookback=3, skip=1)["x"].iloc[3] == pytest.approx(121 / 100 - 1)


def test_volatility_of_constant_growth_is_zero() -> None:
    p = pd.DataFrame({"x": 100 * 1.01 ** np.arange(30)})
    assert volatility(p, 10, 252)["x"].dropna().abs().max() == pytest.approx(0, abs=1e-12)


def test_average_correlation_matches_pairwise() -> None:
    prices = random_prices(60)
    avg = average_correlation(prices, 20)
    at = prices.index[40]
    corr = pairwise_correlation(prices, 20, at)
    expected = (corr.sum() - 1) / (prices.shape[1] - 1)
    pd.testing.assert_series_equal(avg.loc[at], expected, check_names=False)
    assert avg.iloc[:20].isna().all().all()  # needs a full window of returns


def test_build_features_is_lagged_by_one_session() -> None:
    prices = random_prices(30)
    feats = build_features(prices, CFG)
    # ret_1 at row t is the return from t-2 to t-1: the latest close known before session t.
    expected = pd.Series(
        np.log(prices.iloc[19].to_numpy() / prices.iloc[18].to_numpy()), index=prices.columns
    )
    pd.testing.assert_series_equal(feats["ret_1"].iloc[20], expected, check_names=False)


def test_warmup_rows_are_exactly_the_nan_rows() -> None:
    prices = random_prices(80)
    feats = build_features(prices, CFG)
    first_complete = int(np.flatnonzero(feats.notna().all(axis=1).to_numpy())[0])
    assert first_complete == warmup_sessions(CFG)  # rows before it are the history it needs


def test_rejects_unsorted_prices() -> None:
    with pytest.raises(ValueError, match="sorted"):
        build_features(random_prices(30).iloc[::-1], CFG)


@settings(max_examples=60, deadline=None)
@given(
    n=st.integers(min_value=15, max_value=60),
    seed=st.integers(min_value=0, max_value=10_000),
    cut=st.floats(min_value=0.0, max_value=1.0),
    scale=st.floats(min_value=0.2, max_value=5.0),
)
def test_no_look_ahead(n: int, seed: int, cut: float, scale: float) -> None:
    """HANDOFF §2.2 / §7 phase 1: perturbing closes at session t and later must not change any
    feature at rows <= t, because the decision for session t is made before t closes."""
    prices = random_prices(n, seed=seed)
    t = int(cut * (n - 1))
    perturbed = prices.copy()
    rng = np.random.default_rng(seed + 1)
    perturbed.iloc[t:] *= scale * rng.uniform(0.5, 1.5, size=perturbed.iloc[t:].shape)

    before = build_features(prices, CFG).iloc[: t + 1]
    after = build_features(perturbed, CFG).iloc[: t + 1]
    pd.testing.assert_frame_equal(before, after)


def test_future_perturbation_does_change_later_rows() -> None:
    """Sanity check that the no-look-ahead test can fail: rows after t do change."""
    prices = random_prices(40)
    perturbed = prices.copy()
    perturbed.iloc[20:] *= 2.0
    perturbed.iloc[25:] *= 0.5
    changed = ~np.isclose(build_features(prices, CFG), build_features(perturbed, CFG), equal_nan=True)
    assert not changed[:21].any()
    assert changed[21:].any()
