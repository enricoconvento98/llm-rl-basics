"""Yahoo Finance daily bars, for research and development (HANDOFF §4: yfinance_dev.py).

Prices are adjusted for splits and dividends (yfinance `auto_adjust=True`). Yahoo occasionally
revises history and has known adjustment glitches, which is why every download goes through
`rltrading.data.quality` and is stored as a hashed snapshot.

Timestamps: a daily bar is stamped at its session's close in UTC (from the trading calendar), so
"available before the decision" can be checked exactly. A bar on a day that is not a session of
its calendar is stamped at 12:00 UTC of that date and flagged by the quality checks.
"""

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf

from rltrading.data.calendars import get_calendar
from rltrading.data.providers.base import BAR_COLUMNS

NON_SESSION_STAMP = pd.Timedelta(hours=12)


def stamp_daily_bars(dates: pd.DatetimeIndex, calendar: str) -> pd.DatetimeIndex:
    """Map naive bar dates to the UTC close of their session (12:00 UTC if not a session)."""
    cal = get_calendar(calendar)
    stamps = []
    for d in dates:
        day = pd.Timestamp(d.date())
        stamps.append(
            cal.session_close(day) if cal.is_session(day) else pd.Timestamp(day, tz="UTC") + NON_SESSION_STAMP
        )
    return pd.DatetimeIndex(stamps).tz_convert("UTC")


def tidy_download(raw: pd.DataFrame, calendars: Mapping[str, str]) -> pd.DataFrame:
    """Turn a yfinance `download` frame (columns: Price x Ticker) into long bars indexed by
    (timestamp, symbol) with BAR_COLUMNS. Rows where a ticker has no data are dropped."""
    frames = []
    for symbol in raw.columns.get_level_values("Ticker").unique():
        df = pd.DataFrame(raw.xs(symbol, axis=1, level="Ticker")).rename(columns=str.lower)
        df = df[list(BAR_COLUMNS)].dropna(how="all", subset=["open", "high", "low", "close"])
        if df.empty:
            continue
        df.index = stamp_daily_bars(pd.DatetimeIndex(df.index), calendars[symbol])
        df["symbol"] = symbol
        frames.append(df)
    if not frames:
        return pd.DataFrame(
            columns=list(BAR_COLUMNS),
            index=pd.MultiIndex.from_arrays([[], []], names=["timestamp", "symbol"]),
        )
    out = pd.concat(frames)
    out.index.name = "timestamp"
    tidy: pd.DataFrame = out.set_index("symbol", append=True).sort_index()[list(BAR_COLUMNS)].astype(float)
    return tidy


class YahooDataProvider:
    """DataProvider backed by yfinance. `calendars` maps each Yahoo symbol to its calendar name."""

    def __init__(self, calendars: Mapping[str, str], timeout: float = 30.0) -> None:
        self.calendars = dict(calendars)
        self.timeout = timeout

    def daily_bars(self, symbols: Sequence[str], start: date, end: date) -> pd.DataFrame:
        unknown = set(symbols) - set(self.calendars)
        if unknown:
            raise KeyError(f"no calendar configured for {sorted(unknown)}")
        raw = yf.download(
            list(symbols),
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),  # yfinance's end is exclusive
            auto_adjust=True,
            actions=False,
            progress=False,
            group_by="column",
            multi_level_index=True,
            threads=True,
            timeout=self.timeout,
        )
        if raw is None or raw.empty:
            raise RuntimeError(f"Yahoo returned no data for {list(symbols)}")
        return tidy_download(raw, self.calendars)

    def intraday_bars(
        self, symbols: Sequence[str], start: datetime, end: datetime, freq: str
    ) -> pd.DataFrame:
        raise NotImplementedError("intraday data comes in Phase 4 (IBKR first, HANDOFF §7)")
