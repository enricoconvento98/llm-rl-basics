"""Parquet storage for bar data, with snapshot metadata for reproducibility (HANDOFF §2.6).

Each dataset is one Parquet file plus a `.meta.json` next to it. The metadata holds a SHA-256 of
the file: that hash is the snapshot id to log with every MLflow run that uses the data.
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SnapshotMeta:
    dataset: str
    sha256: str
    rows: int
    symbols: list[str]
    first: str
    last: str
    created_at: str
    source: dict[str, Any]

    @property
    def snapshot_id(self) -> str:
        return self.sha256[:12]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class ParquetStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, dataset: str) -> Path:
        return self.root / f"{dataset}.parquet"

    def save(self, dataset: str, bars: pd.DataFrame, source: dict[str, Any]) -> SnapshotMeta:
        path = self._path(dataset)
        path.parent.mkdir(parents=True, exist_ok=True)
        bars.sort_index().to_parquet(path)
        ts = bars.index.get_level_values("timestamp")
        meta = SnapshotMeta(
            dataset=dataset,
            sha256=_sha256(path),
            rows=len(bars),
            symbols=sorted(bars.index.get_level_values("symbol").unique()),
            first=ts.min().isoformat(),
            last=ts.max().isoformat(),
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            source=source,
        )
        path.with_suffix(".meta.json").write_text(json.dumps(asdict(meta), indent=1))
        return meta

    def meta(self, dataset: str) -> SnapshotMeta:
        return SnapshotMeta(**json.loads(self._path(dataset).with_suffix(".meta.json").read_text()))

    def load(self, dataset: str, verify: bool = True) -> pd.DataFrame:
        path = self._path(dataset)
        if verify and _sha256(path) != self.meta(dataset).sha256:
            raise ValueError(f"{path} does not match its snapshot hash: it was modified after download")
        return pd.read_parquet(path)


class ParquetDataProvider:
    """DataProvider over a stored dataset: what backtests read (runtime config `parquet_store`)."""

    def __init__(self, store: ParquetStore, dataset: str) -> None:
        self.store = store
        self.dataset = dataset

    def daily_bars(self, symbols: Sequence[str], start: date, end: date) -> pd.DataFrame:
        bars = self.store.load(self.dataset)
        days = pd.DatetimeIndex(bars.index.get_level_values("timestamp")).date
        in_range = (days >= start) & (days <= end)
        selected: pd.DataFrame = bars[in_range & bars.index.get_level_values("symbol").isin(list(symbols))]
        return selected

    def intraday_bars(
        self, symbols: Sequence[str], start: datetime, end: datetime, freq: str
    ) -> pd.DataFrame:
        raise NotImplementedError("intraday data comes in Phase 4")
