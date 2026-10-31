"""Download -> quality -> store -> fx conversion -> features -> report, with yfinance faked."""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yfinance as yf

from rltrading.config import FeaturesConfig, QualityConfig, UniverseConfig, load_yaml
from rltrading.data import download, report
from rltrading.data.calendars import sessions
from rltrading.data.store import ParquetStore

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"
START, END = date(2023, 1, 1), date(2025, 6, 30)


def fake_market(universe: UniverseConfig) -> dict[str, pd.Series]:
    """Daily closes by Yahoo symbol. Each trading listing = its research ETF converted to EUR,
    so the research-vs-trading check has a known answer (they track each other closely)."""
    rng = np.random.default_rng(7)
    days = pd.bdate_range(START, END)
    eurusd = pd.Series(1.1 * np.exp(rng.normal(0, 0.004, len(days)).cumsum()), index=days)
    closes = {"EURUSD=X": eurusd}
    for asset_id in universe.asset_ids:
        research = universe.listing(asset_id, "research").data_symbols["yahoo"]
        trading = universe.listing(asset_id, "trading")
        usd = pd.Series(100 * np.exp(rng.normal(0.0003, 0.01, len(days)).cumsum()), index=days)
        closes[research] = usd.loc[sessions("XNYS", START, END)]
        native = usd if trading.currency == "USD" else usd / eurusd
        closes[trading.data_symbols["yahoo"]] = native.loc[sessions("XETR", START, END)]
    return closes


@pytest.fixture
def universe() -> UniverseConfig:
    return load_yaml(CONFIG_DIR / "universe.yaml", UniverseConfig)


@pytest.fixture
def fake_yahoo(monkeypatch: pytest.MonkeyPatch, universe: UniverseConfig) -> None:
    closes = fake_market(universe)

    def fake_download(tickers: list[str], **kwargs: object) -> pd.DataFrame:
        frames = {}
        for t in tickers:
            c = closes[t]
            frames[t] = pd.DataFrame(
                {"Close": c, "High": c * 1.005, "Low": c * 0.995, "Open": c, "Volume": 1e6}
            )
        wide = pd.concat(frames, axis=1, names=["Ticker", "Price"]).swaplevel(axis=1).sort_index(axis=1)
        wide.index.name = "Date"
        return wide

    monkeypatch.setattr(yf, "download", fake_download)


@pytest.mark.usefixtures("fake_yahoo")
def test_fetch_and_report(tmp_path: Path, universe: UniverseConfig) -> None:
    store = ParquetStore(tmp_path / "data")
    quality = load_yaml(CONFIG_DIR / "data_quality.yaml", QualityConfig)
    assert download.fetch(universe, quality, store, END)

    research = store.load("daily/yahoo/research")
    assert set(research.index.get_level_values("symbol")) == {"SPY", "VGK", "IEF", "TLT", "GLD"}
    assert store.meta("daily/yahoo/trading").snapshot_id

    closes = report.base_currency_closes(store, universe, "research")
    assert list(closes.columns) == universe.asset_ids
    assert pd.DatetimeIndex(closes.index).tz is not None

    features = load_yaml(CONFIG_DIR / "features.yaml", FeaturesConfig)
    path = report.build_report(store, universe, features, tmp_path / "report")
    text = path.read_text()
    for section in (
        "## Snapshots",
        "## Coverage and quality",
        "## Research vs trading listings",
        "## Feature sanity",
    ):
        assert section in text
    for png in ("coverage", "prices_research", "prices_trading", "features", "correlation"):
        assert (path.parent / f"{png}.png").stat().st_size > 0

    check = report.mapping_check(closes, report.base_currency_closes(store, universe, "trading"))
    assert (check["weekly_return_corr"] > 0.95).all()  # trading = research in EUR, up to close timing


def test_dataset_specs_cover_every_listing(universe: UniverseConfig) -> None:
    specs = {s.name: s.calendars for s in download.dataset_specs(universe)}
    assert specs["daily/yahoo/research"]["SPY"] == "XNYS"
    assert specs["daily/yahoo/trading"]["SXR8.DE"] == "XETR"
    assert specs["daily/yahoo/fx"] == {"EURUSD=X": "24/5"}


def test_check_listing() -> None:
    fund = {"symbol": "IMAE.AS", "longname": "iShares Core MSCI Europe UCITS ETF EUR (Acc)"}
    good = {"symbol": "EUNK.DE", "longname": fund["longname"]}
    other = {"symbol": "SXR7.DE", "longname": "iShares Core MSCI EMU UCITS ETF EUR (Acc)"}
    assert download.check_listing([fund], [good], "EUNK.DE", "EUR", "EUR") == []
    assert len(download.check_listing([fund], [other], "SXR7.DE", "EUR", "EUR")) == 1
    assert len(download.check_listing([fund], [good], "EUNK.DE", "USD", "EUR")) == 1
    assert download.check_listing([fund], [], "EUNK.DE", "EUR", "EUR") == ["EUNK.DE not found on Yahoo"]
    assert download.check_listing([], [good], "EUNK.DE", "EUR", "EUR") == []  # ISIN unknown: name unchecked
