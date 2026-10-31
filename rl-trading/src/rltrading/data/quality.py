"""Data quality checks for daily bars: gaps, duplicates, stale prices, bad prints, split anomalies.

Every check returns issues instead of fixing anything silently. The report says what was found;
a human decides what to do about it.
"""

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from rltrading.config import QualityConfig
from rltrading.data.calendars import get_calendar

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Issue:
    symbol: str
    check: str
    severity: Severity
    detail: str
    timestamp: pd.Timestamp | None = None


@dataclass
class QualityReport:
    summary: pd.DataFrame  # one row per symbol
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def issues_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [vars(i) for i in self.issues], columns=["symbol", "check", "severity", "detail", "timestamp"]
        )


def _session_dates(ts: pd.DatetimeIndex, calendar: str) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Session date of each bar timestamp, and whether the timestamp is exactly that session's close.

    Looked up through the calendar's own close times, because a close can fall on the next calendar
    day (the 24/5 FX session of Monday closes at 00:00 UTC on Tuesday). Timestamps that are not a
    session close (bars stamped at 12:00 UTC on a closed day) map to their UTC date.
    """
    cal = get_calendar(calendar)
    closes = cal.closes
    close_times = pd.DatetimeIndex(closes)
    close_times = close_times.tz_localize("UTC") if close_times.tz is None else close_times.tz_convert("UTC")
    close_to_session = pd.Series(closes.index, index=close_times)
    looked_up = pd.Series(ts.map(close_to_session.get), index=ts)
    on_close = looked_up.notna().to_numpy()
    fallback = pd.Series(ts.tz_convert("UTC").tz_localize(None).normalize(), index=ts)
    return pd.DatetimeIndex(looked_up.where(on_close, fallback)), on_close


def check_symbol(
    bars: pd.DataFrame, symbol: str, calendar: str, cfg: QualityConfig
) -> tuple[dict[str, object], list[Issue]]:
    """Run every check on one symbol's bars (indexed by timestamp)."""
    issues: list[Issue] = []
    cal = get_calendar(calendar)
    ts = pd.DatetimeIndex(bars.index)
    dates, on_close = _session_dates(ts, calendar)

    if dup := int(ts.duplicated().sum()):
        issues.append(Issue(symbol, "duplicates", "error", f"{dup} duplicate timestamps"))

    off_session = ~on_close
    if n := int(off_session.sum()):
        first = ts[off_session][0]
        issues.append(
            Issue(symbol, "non_session_bars", "warning", f"{n} bars on days the exchange is closed", first)
        )

    expected = cal.sessions_in_range(dates.min(), dates.max())
    missing = expected.difference(dates)
    missing_share = len(missing) / max(len(expected), 1)
    if len(missing):
        sev: Severity = "error" if missing_share > cfg.max_missing_share else "warning"
        issues.append(
            Issue(
                symbol,
                "missing_sessions",
                sev,
                f"{len(missing)} of {len(expected)} sessions missing ({missing_share:.2%})",
                pd.Timestamp(missing[0]),
            )
        )

    prices = bars[["open", "high", "low", "close"]]
    if n := int((prices <= 0).any(axis=1).sum()):
        issues.append(Issue(symbol, "non_positive_price", "error", f"{n} bars with a price <= 0"))
    bad_ohlc = (bars["high"] < bars[["open", "close", "low"]].max(axis=1)) | (
        bars["low"] > bars[["open", "close"]].min(axis=1)
    )
    if n := int(bad_ohlc.sum()):
        issues.append(
            Issue(
                symbol,
                "ohlc_inconsistent",
                "warning",
                f"{n} bars where high/low don't bracket open/close",
                pd.Timestamp(ts[bad_ohlc.to_numpy()][0]),
            )
        )

    close = bars["close"]
    runs = (close.diff() != 0).cumsum()
    run_lengths = close.groupby(runs).transform("size")
    stale = run_lengths >= cfg.stale_run_sessions
    if stale.any():
        n_runs = int(runs[stale].nunique())
        issues.append(
            Issue(
                symbol,
                "stale_prices",
                "warning",
                f"{n_runs} runs of >= {cfg.stale_run_sessions} sessions with an unchanged close",
                pd.Timestamp(ts[stale.to_numpy()][0]),
            )
        )

    log_ret = pd.Series(np.log(close.to_numpy()), index=ts).diff()
    for i in (int(k) for k in np.flatnonzero(log_ret.abs().to_numpy() > cfg.jump_abs_log_return)):
        move = float(log_ret.iloc[i])
        nxt = float(log_ret.iloc[i + 1]) if i + 1 < len(log_ret) else 0.0
        reverted = np.sign(nxt) == -np.sign(move) and abs(nxt) >= cfg.jump_reversal_ratio * abs(move)
        kind = "bad print (reverted next day)" if reverted else "large move (check for an unadjusted split)"
        issues.append(
            Issue(
                symbol, "jump", "error" if reverted else "warning", f"{kind}: log return {move:+.2f}", ts[i]
            )
        )

    summary: dict[str, object] = {
        "symbol": symbol,
        "first": dates.min().date(),
        "last": dates.max().date(),
        "years": round((dates.max() - dates.min()).days / 365.25, 1),
        "bars": len(bars),
        "expected_sessions": len(expected),
        "missing_sessions": len(missing),
        "largest_gap_sessions": _largest_gap(expected, dates),
        "errors": sum(i.severity == "error" for i in issues),
        "warnings": sum(i.severity == "warning" for i in issues),
    }
    return summary, issues


def _largest_gap(expected: pd.DatetimeIndex, present: pd.DatetimeIndex) -> int:
    missing = ~expected.isin(present)
    if not missing.any():
        return 0
    groups = (~missing).cumsum()
    return int(pd.Series(missing).groupby(groups).sum().max())


def check_bars(bars: pd.DataFrame, calendars: dict[str, str], cfg: QualityConfig) -> QualityReport:
    """Check long bars indexed by (timestamp, symbol). `calendars` maps symbol -> calendar name."""
    rows, issues = [], []
    for symbol, df in bars.groupby(level="symbol", sort=True):
        summary, found = check_symbol(df.droplevel("symbol"), str(symbol), calendars[str(symbol)], cfg)
        rows.append(summary)
        issues.extend(found)
    return QualityReport(pd.DataFrame(rows).set_index("symbol"), issues)
