"""Features for the agents' state. Pure functions: no I/O, no global state (HANDOFF §4).

All functions take `prices`: a wide frame of closes (rows = sessions in time order, columns =
assets) and return a frame of the same shape where row t only uses closes at rows <= t.

`build_features` then shifts everything by one session, so its row t only uses closes strictly
before t. That is the decision-time convention used everywhere: the decision for session t is
made before session t closes, with everything known up to the previous close (HANDOFF §2.2).
"""

import numpy as np
import pandas as pd

from rltrading.config import FeaturesConfig


def log_returns(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    """log(p_t / p_{t-window})."""
    ratio: pd.DataFrame = prices / prices.shift(window)
    return ratio.apply(np.log)


def volatility(prices: pd.DataFrame, window: int, sessions_per_year: int) -> pd.DataFrame:
    """Annualized standard deviation of daily log returns over the last `window` sessions."""
    vol: pd.DataFrame = log_returns(prices, 1).rolling(window, min_periods=window).std()
    return vol * float(np.sqrt(sessions_per_year))


def momentum(prices: pd.DataFrame, lookback: int, skip: int) -> pd.DataFrame:
    """Return from `lookback` sessions ago to `skip` sessions ago: p_{t-skip} / p_{t-lookback} - 1."""
    return prices.shift(skip) / prices.shift(lookback) - 1


def average_correlation(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    """Each asset's mean rolling correlation of daily log returns with every other asset."""
    rets = log_returns(prices, 1)
    corr = rets.rolling(window, min_periods=window).corr()  # rows: (timestamp, asset)
    n = prices.shape[1]
    # Each asset's row sums its correlation with itself (1.0) plus the others.
    avg = (corr.groupby(level=0, sort=False).sum(min_count=1) - 1.0) / (n - 1)
    avg = avg.where(corr.groupby(level=0, sort=False).count() == n)  # NaN until the window is full
    return avg.reindex(prices.index)[prices.columns]


def pairwise_correlation(prices: pd.DataFrame, window: int, at: pd.Timestamp) -> pd.DataFrame:
    """Correlation matrix of daily log returns over the `window` sessions ending at `at` (inclusive)."""
    rets = log_returns(prices, 1).loc[:at].tail(window)
    return rets.corr()


def build_features(prices: pd.DataFrame, cfg: FeaturesConfig) -> pd.DataFrame:
    """All state features, aligned to decision time.

    Returns columns (feature, asset). Row t uses only closes at rows < t. The first rows are NaN
    until the longest window has enough history.
    """
    if not prices.index.is_monotonic_increasing:
        raise ValueError("prices must be sorted by time")
    parts: dict[str, pd.DataFrame] = {}
    for w in cfg.return_windows:
        parts[f"ret_{w}"] = log_returns(prices, w)
    for w in cfg.volatility_windows:
        parts[f"vol_{w}"] = volatility(prices, w, cfg.sessions_per_year)
    parts[f"mom_{cfg.momentum.lookback}_{cfg.momentum.skip}"] = momentum(
        prices, cfg.momentum.lookback, cfg.momentum.skip
    )
    if prices.shape[1] > 1:
        parts[f"avg_corr_{cfg.correlation_window}"] = average_correlation(prices, cfg.correlation_window)
    features = pd.concat(parts, axis=1, names=["feature", "asset"])
    return features.shift(1)  # decision-time alignment: row t sees closes up to t-1 only


def warmup_sessions(cfg: FeaturesConfig) -> int:
    """Sessions of history needed before every feature is defined (including the 1-session lag)."""
    longest = max(
        [
            *cfg.return_windows,
            *(w + 1 for w in cfg.volatility_windows),
            cfg.momentum.lookback,
            cfg.correlation_window + 1,
        ]
    )
    return longest + 1
