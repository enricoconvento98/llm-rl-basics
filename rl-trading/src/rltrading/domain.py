"""Domain objects shared by every layer and every run mode (HANDOFF §5).

All objects are immutable and validate themselves on creation, so an invalid order can never
travel through the pipeline. Timestamps must be timezone-aware UTC.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import NewType

OrderId = NewType("OrderId", str)

# Floating-point slack when checking that weights sum to at most 1.
WEIGHT_SUM_TOLERANCE = 1e-9


class RunMode(StrEnum):
    BACKTEST = "backtest"
    SHADOW = "shadow"
    PAPER = "paper"
    LIVE = "live"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MKT"
    LIMIT = "LMT"


class TimeInForce(StrEnum):
    DAY = "DAY"
    IOC = "IOC"
    GTC = "GTC"


def _require_utc(ts: datetime, name: str) -> None:
    if ts.tzinfo is None or ts.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be timezone-aware UTC, got {ts!r}")


def _require_positive(value: float, name: str) -> None:
    if not value > 0:
        raise ValueError(f"{name} must be > 0, got {value}")


def _require_symbol(symbol: str) -> None:
    if not symbol or symbol != symbol.strip():
        raise ValueError(f"invalid symbol {symbol!r}")


@dataclass(frozen=True, slots=True)
class TargetWeights:
    """Output of the allocation layer: fraction of portfolio value per asset.

    Long-only and unlevered (HANDOFF §1 non-goals): every weight is in [0, 1] and they sum to at
    most 1. Whatever is left over is cash.
    """

    ts: datetime
    weights: Mapping[str, float]

    def __post_init__(self) -> None:
        _require_utc(self.ts, "ts")
        for symbol, weight in self.weights.items():
            _require_symbol(symbol)
            if not 0.0 <= weight <= 1.0:
                raise ValueError(
                    f"weight for {symbol} must be in [0, 1] (no shorts, no leverage), got {weight}"
                )
        if sum(self.weights.values()) > 1.0 + WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"weights sum to {sum(self.weights.values())}, more than 1 (no leverage)")
        # Freeze the mapping so callers can't mutate it after validation.
        object.__setattr__(self, "weights", MappingProxyType(dict(self.weights)))

    @property
    def cash(self) -> float:
        return max(0.0, 1.0 - sum(self.weights.values()))


@dataclass(frozen=True, slots=True)
class ParentOrder:
    """A whole order handed from allocation to execution, to be filled before `deadline`."""

    symbol: str
    side: Side
    qty: float
    created_at: datetime
    deadline: datetime
    id: str = ""

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        _require_positive(self.qty, "qty")
        _require_utc(self.created_at, "created_at")
        _require_utc(self.deadline, "deadline")
        if self.deadline <= self.created_at:
            raise ValueError("deadline must be after created_at")


@dataclass(frozen=True, slots=True)
class ChildOrder:
    """One order actually sent to a broker (a slice of a parent order)."""

    symbol: str
    side: Side
    qty: float
    order_type: OrderType
    limit_price: float | None = None
    tif: TimeInForce = TimeInForce.DAY
    parent_id: str | None = field(default=None)

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        _require_positive(self.qty, "qty")
        if self.order_type is OrderType.LIMIT:
            if self.limit_price is None:
                raise ValueError("limit orders need a limit_price")
            _require_positive(self.limit_price, "limit_price")
        elif self.limit_price is not None:
            raise ValueError("market orders must not have a limit_price")


@dataclass(frozen=True, slots=True)
class Fill:
    """An execution reported by a broker (simulated, paper or live)."""

    order_id: OrderId
    symbol: str
    side: Side
    qty: float
    price: float
    ts: datetime
    fees: float = 0.0

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        _require_positive(self.qty, "qty")
        _require_positive(self.price, "price")
        _require_utc(self.ts, "ts")
        if self.fees < 0:
            raise ValueError(f"fees must be >= 0, got {self.fees}")

    @property
    def notional(self) -> float:
        return self.qty * self.price
