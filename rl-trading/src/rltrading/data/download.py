"""Download daily bars for the universe and store them as snapshots.

    python -m rltrading.data.download verify     # check trading listings against Yahoo by ISIN
    python -m rltrading.data.download fetch      # download research, trading and fx bars, run quality checks

Datasets written under Settings.data_dir:
    daily/yahoo/research   US ETFs (native USD)
    daily/yahoo/trading    UCITS listings (native EUR)
    daily/yahoo/fx         exchange rates, one bar per 24/5 session
Each comes with a .meta.json (snapshot hash) and a .quality.json (quality report).
"""

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path

import yfinance as yf

from rltrading.config import QualityConfig, Settings, UniverseConfig, load_yaml
from rltrading.data.providers.yfinance_dev import YahooDataProvider
from rltrading.data.quality import bad_prints, check_bars
from rltrading.data.store import ParquetStore

PROVIDER = "yahoo"
FX_CALENDAR = "24/5"  # FX trades around the clock on weekdays; each bar is stamped at the end of its UTC day


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    calendars: dict[str, str]  # Yahoo symbol -> calendar


def dataset_specs(universe: UniverseConfig) -> list[DatasetSpec]:
    specs = []
    for kind in ("research", "trading"):
        listings = [universe.listing(a, kind) for a in universe.asset_ids]
        specs.append(
            DatasetSpec(
                f"daily/{PROVIDER}/{kind}", {lst.data_symbols[PROVIDER]: lst.calendar for lst in listings}
            )
        )
    specs.append(
        DatasetSpec(f"daily/{PROVIDER}/fx", {fx.data_symbols[PROVIDER]: FX_CALENDAR for fx in universe.fx})
    )
    return specs


def _name(quote: Mapping[str, object]) -> str:
    return str(quote.get("longname") or quote.get("shortname") or "")


def check_listing(
    isin_quotes: list[Mapping[str, object]],
    symbol_quotes: list[Mapping[str, object]],
    symbol: str,
    quoted_currency: str | None,
    currency: str,
) -> list[str]:
    """Problems with one trading listing; empty if it checks out.

    Yahoo's ISIN search returns one listing per fund, usually not ours, so the symbol is matched
    by fund name against that listing rather than by being among the results."""
    own = next((q for q in symbol_quotes if q.get("symbol") == symbol), None)
    if own is None:
        return [f"{symbol} not found on Yahoo"]
    problems = []
    if isin_quotes and _name(own) not in {_name(q) for q in isin_quotes}:
        problems.append(f"{symbol} is {_name(own)!r}, the ISIN is {_name(isin_quotes[0])!r}")
    if quoted_currency != currency:
        problems.append(f"{symbol} is quoted in {quoted_currency}, configured as {currency}")
    return problems


def verify(universe: UniverseConfig) -> bool:
    """Check each trading listing's Yahoo symbol against its ISIN (fund name) and currency."""
    ok = True
    for asset_id in universe.asset_ids:
        lst = universe.listing(asset_id, "trading")
        if lst.isin is None:
            print(f"  {asset_id}: no ISIN configured, skipped")
            continue
        symbol = lst.data_symbols[PROVIDER]
        isin_quotes = yf.Search(lst.isin, max_results=20, news_count=0, lists_count=0).quotes
        symbol_quotes = yf.Search(symbol, max_results=20, news_count=0, lists_count=0).quotes
        problems = check_listing(
            isin_quotes, symbol_quotes, symbol, yf.Ticker(symbol).fast_info.currency, lst.currency
        )
        ok &= not problems
        note = "" if isin_quotes else " (ISIN unknown to Yahoo: name not checked)"
        print(f"  {asset_id}: {lst.isin} -> {symbol}: {'ok' if not problems else 'MISMATCH'}{note}")
        for problem in problems:
            print(f"      {problem}")
    return ok


def fetch(universe: UniverseConfig, quality_cfg: QualityConfig, store: ParquetStore, end: date) -> bool:
    all_ok = True
    for spec in dataset_specs(universe):
        provider = YahooDataProvider(spec.calendars)
        raw = provider.daily_bars(list(spec.calendars), universe.start_date, end)
        dropped = bad_prints(raw, spec.calendars, quality_cfg)
        bars = raw.drop(dropped)
        source = {
            "provider": PROVIDER,
            "yfinance": version("yfinance"),
            "auto_adjust": True,
            "requested_start": universe.start_date.isoformat(),
            "requested_end": end.isoformat(),
            "dropped_bad_prints": len(dropped),
        }
        meta = store.save(spec.name, bars, source)
        report = check_bars(bars, spec.calendars, quality_cfg)
        quality_path = store.root / f"{spec.name}.quality.json"
        quality_path.write_text(
            json.dumps(
                {
                    "snapshot_id": meta.snapshot_id,
                    "summary": json.loads(report.summary.to_json(orient="index", date_format="iso")),
                    "issues": json.loads(report.issues_frame().to_json(orient="records", date_format="iso")),
                    "dropped_bad_prints": [{"timestamp": t.isoformat(), "symbol": s} for t, s in dropped],
                },
                indent=1,
            )
        )
        all_ok &= report.ok
        print(
            f"{spec.name}: {meta.rows} rows, {len(meta.symbols)} symbols, snapshot {meta.snapshot_id}, "
            f"{len(dropped)} bad prints dropped, {len(report.errors)} errors, "
            f"{len(report.issues) - len(report.errors)} warnings"
        )
        print(report.summary.to_string())
    return all_ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["verify", "fetch"])
    parser.add_argument(
        "--end", type=date.fromisoformat, default=None, help="last day (default: universe end or today)"
    )
    args = parser.parse_args(argv)

    settings = Settings()
    universe = load_yaml(settings.config_dir / "universe.yaml", UniverseConfig)
    if args.command == "verify":
        return 0 if verify(universe) else 1
    end = args.end or universe.end_date or datetime.now(UTC).date()
    quality_cfg = load_yaml(settings.config_dir / "data_quality.yaml", QualityConfig)
    ok = fetch(universe, quality_cfg, ParquetStore(Path(settings.data_dir)), end)
    print(
        "quality: OK" if ok else "quality: ERRORS found, see the .quality.json files before using this data"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
