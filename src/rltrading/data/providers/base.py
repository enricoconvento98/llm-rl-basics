"""Data provider interfaces (HANDOFF §5).

Bar frames have a (timestamp, symbol) MultiIndex, timestamps in UTC, and the columns in
`BAR_COLUMNS`. Daily bars are adjusted for splits and dividends.
"""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Final, Protocol, runtime_checkable

import pandas as pd

BAR_COLUMNS: Final = ("open", "high", "low", "close", "volume")
QUOTE_COLUMNS: Final = ("bid", "ask", "bid_size", "ask_size")


@runtime_checkable
class DataProvider(Protocol):
    def daily_bars(self, symbols: Sequence[str], start: date, end: date) -> pd.DataFrame:
        """Adjusted daily OHLCV bars for `symbols`, from `start` to `end` inclusive."""
        ...

    def intraday_bars(self, symbols: Sequence[str], start: datetime, end: datetime, freq: str) -> pd.DataFrame:
        """Intraday OHLCV bars at frequency `freq` (a pandas offset alias such as "1min" or "5min")."""
        ...


@runtime_checkable
class QuoteProvider(Protocol):
    """Optional capability: not every provider has bid/ask quotes."""

    def quotes(self, symbols: Sequence[str], start: datetime, end: datetime) -> pd.DataFrame:
        """Top-of-book quotes with the columns in `QUOTE_COLUMNS`."""
        ...
