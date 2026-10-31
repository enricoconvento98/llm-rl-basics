from datetime import date

import numpy as np
import pandas as pd
import pytest

from rltrading.config import QualityConfig
from rltrading.data.calendars import sessions
from rltrading.data.fx import to_base_currency
from rltrading.data.providers.base import BAR_COLUMNS, DataProvider
from rltrading.data.providers.yfinance_dev import NON_SESSION_STAMP, stamp_daily_bars, tidy_download
from rltrading.data.quality import check_bars
from rltrading.data.store import ParquetDataProvider, ParquetStore

QCFG = QualityConfig(
    stale_run_sessions=5, jump_abs_log_return=0.2, jump_reversal_ratio=0.8, max_missing_share=0.01
)


def make_bars(symbol: str, calendar: str, start: date, end: date, seed: int = 0) -> pd.DataFrame:
    days = sessions(calendar, start, end)
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(rng.normal(0, 0.01, len(days)).cumsum())
    df = pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 1e6},
        index=stamp_daily_bars(days, calendar),
    )
    df.index.name = "timestamp"
    df["symbol"] = symbol
    return df.set_index("symbol", append=True)


# ---------------------------------------------------------------- calendars and stamping


def test_bars_are_stamped_at_the_session_close_in_utc() -> None:
    stamps = stamp_daily_bars(pd.DatetimeIndex(["2026-01-02", "2026-07-02"]), "XNYS")
    assert [str(s) for s in stamps] == [
        "2026-01-02 21:00:00+00:00",
        "2026-07-02 20:00:00+00:00",
    ]  # EST vs EDT
    xetra = stamp_daily_bars(pd.DatetimeIndex(["2026-01-02"]), "XETR")
    assert str(xetra[0]) == "2026-01-02 16:30:00+00:00"


def test_non_session_days_get_the_flag_stamp() -> None:
    christmas = stamp_daily_bars(pd.DatetimeIndex(["2025-12-25"]), "XNYS")
    assert christmas[0] == pd.Timestamp("2025-12-25", tz="UTC") + NON_SESSION_STAMP


def test_calendars_reach_back_before_their_20_year_default() -> None:
    assert sessions("XNYS", date(2005, 1, 3), date(2005, 1, 7)).size == 5


# ---------------------------------------------------------------- yfinance download parsing


def yfinance_like_frame() -> pd.DataFrame:
    """Shape of yf.download(..., group_by='column', multi_level_index=True): columns (Price, Ticker)."""
    idx = pd.DatetimeIndex(["2026-01-02", "2026-01-05", "2026-01-06"], name="Date")
    cols = pd.MultiIndex.from_product(
        [["Close", "High", "Low", "Open", "Volume"], ["SPY", "SXR8.DE"]], names=["Price", "Ticker"]
    )
    data = np.arange(30, dtype=float).reshape(3, 10) + 1
    df = pd.DataFrame(data, index=idx, columns=cols)
    df.loc["2026-01-06", (slice(None), "SXR8.DE")] = np.nan  # SXR8 missing one day
    return df


def test_tidy_download() -> None:
    bars = tidy_download(yfinance_like_frame(), {"SPY": "XNYS", "SXR8.DE": "XETR"})
    assert list(bars.columns) == list(BAR_COLUMNS)
    assert bars.index.names == ["timestamp", "symbol"]
    assert bars.xs("SPY", level="symbol").shape[0] == 3
    assert bars.xs("SXR8.DE", level="symbol").shape[0] == 2  # the all-NaN day is dropped
    first_spy = bars.xs("SPY", level="symbol").iloc[0]
    assert first_spy["close"] == 1.0
    assert first_spy["open"] == 7.0


# ---------------------------------------------------------------- quality


def test_clean_data_has_no_issues() -> None:
    bars = make_bars("SPY", "XNYS", date(2024, 1, 1), date(2024, 12, 31))
    report = check_bars(bars, {"SPY": "XNYS"}, QCFG)
    assert report.ok
    assert not report.issues
    assert report.summary.loc["SPY", "missing_sessions"] == 0


def test_quality_finds_each_problem() -> None:
    bars = make_bars("SPY", "XNYS", date(2024, 1, 1), date(2024, 12, 31)).droplevel("symbol")
    bars = bars.drop(bars.index[50:60])  # a 10-session gap
    close, high, low = (bars[c].to_numpy(copy=True) for c in ("close", "high", "low"))
    close[100:107] = 50.0  # stale run of 7 identical closes
    close[150] *= 2.0  # bad print, reverted next day
    high[150] *= 2.0
    low[5] = -1.0  # negative price
    bars["close"], bars["high"], bars["low"] = close, high, low
    halved = bars.index[200:]
    bars.loc[halved, ["open", "high", "low", "close"]] = (
        bars.loc[halved, ["open", "high", "low", "close"]] * 0.5
    )
    bars = pd.concat([bars, bars.iloc[[10]]]).sort_index()  # a duplicate
    bars["symbol"] = "SPY"
    report = check_bars(bars.set_index("symbol", append=True), {"SPY": "XNYS"}, QCFG)
    found = {(i.check, i.severity) for i in report.issues}
    assert ("duplicates", "error") in found
    assert ("missing_sessions", "error") in found  # 10 of ~250 sessions > 1%
    assert ("stale_prices", "warning") in found
    assert ("non_positive_price", "error") in found
    assert ("jump", "error") in found  # the reverted bad print
    assert ("jump", "warning") in found  # the split-like move
    assert report.summary.loc["SPY", "largest_gap_sessions"] == 10
    assert not report.ok


def test_bar_on_a_holiday_is_flagged() -> None:
    bars = make_bars("SPY", "XNYS", date(2025, 12, 1), date(2025, 12, 31)).droplevel("symbol")
    holiday = bars.iloc[[0]].copy()
    holiday.index = stamp_daily_bars(pd.DatetimeIndex(["2025-12-25"]), "XNYS")
    bars = pd.concat([bars, holiday]).sort_index()
    bars["symbol"] = "SPY"
    report = check_bars(bars.set_index("symbol", append=True), {"SPY": "XNYS"}, QCFG)
    assert [i.check for i in report.issues] == ["non_session_bars"]


# ---------------------------------------------------------------- fx


def test_fx_conversion_uses_only_rates_known_at_the_bar() -> None:
    bars = make_bars("SPY", "XNYS", date(2026, 1, 5), date(2026, 1, 7))
    # A rate stamped at 00:00 UTC on Jan 6 (end of the Jan 5 FX day) and one on Jan 7, both
    # before the respective US closes; the rate stamped at 23:00 on Jan 7 is after the Jan 7 close.
    rates = pd.Series(
        [1.0, 1.25, 2.0, 99.0],
        index=pd.DatetimeIndex(
            ["2026-01-05 00:00", "2026-01-06 00:00", "2026-01-07 00:00", "2026-01-07 23:00"], tz="UTC"
        ),
    )
    eur = to_base_currency(bars, {"SPY": "USD"}, {"USD": rates}, "EUR")
    ratio = (bars["close"] / eur["close"]).to_numpy()
    np.testing.assert_allclose(ratio, [1.0, 1.25, 2.0])
    assert (eur["volume"] == bars["volume"]).all()


def test_fx_conversion_needs_an_earlier_rate() -> None:
    bars = make_bars("SPY", "XNYS", date(2026, 1, 5), date(2026, 1, 7))
    late = pd.Series([1.1], index=pd.DatetimeIndex(["2026-02-01"], tz="UTC"))
    with pytest.raises(ValueError, match="no USD rate"):
        to_base_currency(bars, {"SPY": "USD"}, {"USD": late}, "EUR")


def test_base_currency_listings_are_untouched() -> None:
    bars = make_bars("SXR8.DE", "XETR", date(2026, 1, 5), date(2026, 1, 7))
    pd.testing.assert_frame_equal(to_base_currency(bars, {"SXR8.DE": "EUR"}, {}, "EUR"), bars)


# ---------------------------------------------------------------- store


def test_store_roundtrip_and_snapshot_hash(tmp_path: pytest.TempPathFactory) -> None:
    store = ParquetStore(tmp_path)  # type: ignore[arg-type]
    bars = pd.concat(
        [
            make_bars("SPY", "XNYS", date(2024, 1, 1), date(2024, 3, 1)),
            make_bars("IEF", "XNYS", date(2024, 1, 1), date(2024, 3, 1), seed=1),
        ]
    )
    meta = store.save("daily/yahoo/research", bars, {"provider": "test"})
    assert meta.rows == len(bars)
    assert meta.symbols == ["IEF", "SPY"]
    assert len(meta.snapshot_id) == 12
    pd.testing.assert_frame_equal(store.load("daily/yahoo/research"), bars.sort_index())

    provider = ParquetDataProvider(store, "daily/yahoo/research")
    assert isinstance(provider, DataProvider)
    jan = provider.daily_bars(["SPY"], date(2024, 1, 1), date(2024, 1, 31))
    assert set(jan.index.get_level_values("symbol")) == {"SPY"}
    assert len(jan) == len(sessions("XNYS", date(2024, 1, 1), date(2024, 1, 31)))


def test_store_detects_modified_files(tmp_path: pytest.TempPathFactory) -> None:
    store = ParquetStore(tmp_path)  # type: ignore[arg-type]
    bars = make_bars("SPY", "XNYS", date(2024, 1, 1), date(2024, 2, 1))
    store.save("d", bars, {})
    bars.iloc[:3].to_parquet(tmp_path / "d.parquet")  # type: ignore[operator]
    with pytest.raises(ValueError, match="snapshot hash"):
        store.load("d")


def test_fx_bars_on_the_24_5_calendar_have_no_gaps() -> None:
    """Regression: a 24/5 session closes at 00:00 UTC on the next day, which must still map back to
    its own session date (it used to be read as the next day, showing every Monday as missing)."""
    bars = make_bars("EURUSD=X", "24/5", date(2025, 1, 1), date(2025, 3, 31))
    report = check_bars(bars, {"EURUSD=X": "24/5"}, QCFG)
    assert not report.issues
    assert report.summary.loc["EURUSD=X", "missing_sessions"] == 0
