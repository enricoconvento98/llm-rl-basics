"""Conversion of bar prices into the base currency."""

from collections.abc import Mapping

import pandas as pd

PRICE_COLUMNS = ["open", "high", "low", "close"]


def to_base_currency(
    bars: pd.DataFrame,
    currency_of: Mapping[str, str],
    fx_closes: Mapping[str, pd.Series],
    base_currency: str,
) -> pd.DataFrame:
    """Convert OHLC prices to the base currency. Volume is left unchanged.

    `fx_closes[ccy]` is a series of rates (units of `ccy` per 1 base unit) indexed by UTC timestamp.
    Each bar uses the latest rate stamped at or before the bar's own timestamp, so conversion never
    uses a rate that wasn't known yet when the bar closed.
    """
    out = []
    for symbol, group in bars.groupby(level="symbol", sort=False):
        ccy = currency_of[str(symbol)]
        df = group.copy()
        if ccy != base_currency:
            rate = fx_closes[ccy].sort_index()
            ts = df.index.get_level_values("timestamp")
            aligned = rate.reindex(rate.index.union(ts)).ffill().reindex(ts)
            if aligned.isna().any():
                raise ValueError(f"{symbol}: no {ccy} rate before {ts[aligned.isna().to_numpy()][0]}")
            df[PRICE_COLUMNS] = df[PRICE_COLUMNS].div(aligned.to_numpy(), axis=0)
        out.append(df)
    return pd.concat(out).sort_index()
