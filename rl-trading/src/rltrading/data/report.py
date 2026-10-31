"""Phase 1 gate report: data coverage, quality issues and feature sanity plots.

    python -m rltrading.data.report --out reports/phase1

Reads the stored snapshots (run `python -m rltrading.data.download fetch` first) and writes a
Markdown report plus PNG charts. Prices are converted to the base currency before features are
computed, exactly as the agents will see them.
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from rltrading.config import FeaturesConfig, ListingKind, Settings, UniverseConfig, load_yaml
from rltrading.data.download import PROVIDER
from rltrading.data.fx import to_base_currency
from rltrading.data.store import ParquetStore
from rltrading.features import build_features
from rltrading.features.core import pairwise_correlation

# Below this many overlapping weeks the research-vs-trading comparison means nothing.
MIN_OVERLAP_WEEKS = 26
WEEKS_PER_YEAR = 52
# The correlation heatmap covers this many correlation windows (63 sessions x 4 = about a year).
HEATMAP_WINDOWS = 4


def base_currency_closes(store: ParquetStore, universe: UniverseConfig, kind: ListingKind) -> pd.DataFrame:
    """Wide frame of closes in the base currency: rows = timestamps, columns = asset ids."""
    bars = store.load(f"daily/{PROVIDER}/{kind}")
    fx = store.load(f"daily/{PROVIDER}/fx")
    listings = {a: universe.listing(a, kind) for a in universe.asset_ids}
    symbol_to_asset = {lst.data_symbols[PROVIDER]: a for a, lst in listings.items()}
    currency_of = {lst.data_symbols[PROVIDER]: lst.currency for lst in listings.values()}
    fx_closes = {f.currency: fx.xs(f.data_symbols[PROVIDER], level="symbol")["close"] for f in universe.fx}
    converted = to_base_currency(bars, currency_of, fx_closes, universe.base_currency)
    wide = converted["close"].unstack("symbol").rename(columns=symbol_to_asset)
    return wide[[a for a in universe.asset_ids if a in wide.columns]]


def _save(fig: Figure, path: Path) -> str:
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path.name


def coverage_chart(closes: dict[str, pd.DataFrame], out: Path) -> str:
    fig, ax = plt.subplots(figsize=(10, 3.2))
    labels = []
    for i, (kind, wide) in enumerate(closes.items()):
        for j, asset in enumerate(wide.columns):
            have = wide[asset].dropna().index
            y = i * (len(wide.columns) + 1) + j
            ax.plot([have.min(), have.max()], [y, y], linewidth=6, solid_capstyle="butt")
            labels.append((y, f"{asset} ({kind})"))
    ax.set_yticks([y for y, _ in labels], [label for _, label in labels], fontsize=8)
    ax.set_title("Data coverage")
    return _save(fig, out / "coverage.png")


def prices_chart(wide: pd.DataFrame, title: str, path: Path) -> str:
    fig, ax = plt.subplots(figsize=(10, 3.6))
    (wide / wide.bfill().iloc[0]).plot(ax=ax, logy=True, linewidth=1)
    ax.set(title=title, ylabel="growth of 1 (log scale)", xlabel="")
    return _save(fig, path)


def features_chart(features: pd.DataFrame, path: Path) -> str:
    names = list(features.columns.get_level_values("feature").unique())
    cols = 3
    rows = int(np.ceil(len(names) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(12, 2.6 * rows), squeeze=False, sharex=True)
    for ax, name in zip(axes.flat, names, strict=False):
        features[name].plot(ax=ax, linewidth=0.7, legend=False)
        ax.set_title(name, fontsize=9)
        ax.set_xlabel("")
    for ax in list(axes.flat)[len(names) :]:
        ax.set_axis_off()
    axes.flat[0].legend(fontsize=7)
    return _save(fig, path)


def correlation_chart(corr: pd.DataFrame, title: str, path: Path) -> str:
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    im = ax.imshow(corr.to_numpy(), vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(corr)), corr.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(corr)), corr.index, fontsize=8)
    for (i, j), v in np.ndenumerate(corr.to_numpy()):
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax)
    ax.set_title(title, fontsize=10)
    return _save(fig, path)


def mapping_check(research: pd.DataFrame, trading: pd.DataFrame) -> pd.DataFrame:
    """How well each UCITS listing tracks its research ETF, both in EUR, on overlapping weeks.

    Weekly (Friday) returns, because the two trade on different exchanges with different closes
    and holidays; daily returns would mostly measure that timing mismatch.
    """
    rows = []
    for asset in research.columns.intersection(trading.columns):
        weekly = pd.concat(
            [
                research[asset].dropna().resample("W-FRI").last(),
                trading[asset].dropna().resample("W-FRI").last(),
            ],
            axis=1,
            keys=["research", "trading"],
        ).dropna()
        rets = weekly.apply(np.log).diff().dropna()
        if len(rets) < MIN_OVERLAP_WEEKS:
            continue
        rows.append(
            {
                "asset": asset,
                "overlap_from": rets.index.min().date(),
                "weeks": len(rets),
                "weekly_return_corr": round(float(rets["research"].corr(rets["trading"])), 3),
                "ann_return_diff_pct": round(
                    float((rets["trading"].mean() - rets["research"].mean()) * WEEKS_PER_YEAR * 100), 2
                ),
                "tracking_error_pct": round(
                    float((rets["trading"] - rets["research"]).std() * np.sqrt(WEEKS_PER_YEAR) * 100), 2
                ),
            }
        )
    return pd.DataFrame(rows).set_index("asset") if rows else pd.DataFrame()


def build_report(
    store: ParquetStore, universe: UniverseConfig, features_cfg: FeaturesConfig, out: Path
) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    closes = {kind: base_currency_closes(store, universe, kind) for kind in ("research", "trading")}
    research_features = build_features(closes["research"].dropna(), features_cfg)

    lines = [
        "# Phase 1 data report\n",
        f"Base currency: **{universe.base_currency}**. Built from the stored snapshots below; "
        "regenerate with `make data-report`.\n",
        "## Snapshots\n",
        "| Dataset | Snapshot | Rows | Symbols | First | Last |",
        "|---|---|---|---|---|---|",
    ]
    for name in ("research", "trading", "fx"):
        m = store.meta(f"daily/{PROVIDER}/{name}")
        symbols = ", ".join(m.symbols)
        lines.append(
            f"| {m.dataset} | `{m.snapshot_id}` | {m.rows} | {symbols} | {m.first[:10]} | {m.last[:10]} |"
        )

    lines += ["\n## Coverage and quality\n", f"![coverage]({coverage_chart(closes, out)})\n"]
    for name in ("research", "trading", "fx"):
        q = json.loads((store.root / f"daily/{PROVIDER}/{name}.quality.json").read_text())
        summary = pd.DataFrame.from_dict(q["summary"], orient="index")
        lines += [f"### {name}\n", summary.to_markdown(), ""]
        issues = pd.DataFrame(q["issues"])
        if issues.empty:
            lines.append("No issues found.\n")
        else:
            lines += [f"{len(issues)} issue(s):\n", issues.to_markdown(index=False), ""]

    research_chart = prices_chart(closes["research"], "Research listings in EUR", out / "prices_research.png")
    trading_chart = prices_chart(closes["trading"], "Trading listings in EUR", out / "prices_trading.png")
    lines += [
        "## Research vs trading listings\n",
        "Does each UCITS listing track its research ETF? Weekly returns in EUR, over the weeks both exist.\n",
        mapping_check(closes["research"], closes["trading"]).to_markdown(),
        "",
        f"![research prices]({research_chart})",
        f"![trading prices]({trading_chart})\n",
    ]

    sessions = features_cfg.correlation_window * HEATMAP_WINDOWS
    last = research_features.dropna().index.max()
    corr = pairwise_correlation(closes["research"].dropna(), sessions, last)
    heatmap = correlation_chart(
        corr, f"Daily return correlation, last {sessions} sessions", out / "correlation.png"
    )
    lines += [
        "## Feature sanity checks (research listings, decision-time aligned)\n",
        f"![features]({features_chart(research_features, out / 'features.png')})\n",
        "Feature summary over the full history:\n",
        research_features.describe().T.round(4).to_markdown(),
        "",
        f"![correlation]({heatmap})\n",
    ]
    path = out / "README.md"
    path.write_text("\n".join(lines))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=Path("reports/phase1"))
    args = parser.parse_args(argv)
    settings = Settings()
    universe = load_yaml(settings.config_dir / "universe.yaml", UniverseConfig)
    features_cfg = load_yaml(settings.config_dir / "features.yaml", FeaturesConfig)
    path = build_report(ParquetStore(Path(settings.data_dir)), universe, features_cfg, args.out)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
