"""In-memory fakes of the interfaces, for tests. They never touch a network (HANDOFF §8)."""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from itertools import count

import numpy as np
import pandas as pd

from rltrading.agents.base import Action, State
from rltrading.data.providers.base import BAR_COLUMNS, QUOTE_COLUMNS
from rltrading.domain import ChildOrder, Fill, OrderId, Side


class FakeBroker:
    """Fills every order immediately at a fixed price."""

    def __init__(self, cash: float, price: float = 100.0) -> None:
        self._cash = cash
        self._price = price
        self._positions: dict[str, float] = {}
        self._fills: list[Fill] = []
        self._open: list[OrderId] = []
        self._ids = count(1)

    def positions(self) -> dict[str, float]:
        return dict(self._positions)

    def cash(self) -> float:
        return self._cash

    def place_order(self, order: ChildOrder) -> OrderId:
        order_id = OrderId(f"fake-{next(self._ids)}")
        sign = 1 if order.side is Side.BUY else -1
        self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) + sign * order.qty
        self._cash -= sign * order.qty * self._price
        self._fills.append(
            Fill(order_id, order.symbol, order.side, order.qty, self._price, datetime.now(UTC))
        )
        return order_id

    def cancel(self, order_id: OrderId) -> None:
        if order_id in self._open:
            self._open.remove(order_id)

    def open_orders(self) -> list[OrderId]:
        return list(self._open)

    def fills(self, since: datetime) -> list[Fill]:
        return [f for f in self._fills if f.ts >= since]


def _bars(symbols: Sequence[str], index: pd.DatetimeIndex) -> pd.DataFrame:
    rows = pd.MultiIndex.from_product([index, list(symbols)], names=["timestamp", "symbol"])
    return pd.DataFrame(100.0, index=rows, columns=list(BAR_COLUMNS))


class FakeDataProvider:
    """Flat prices, one bar per business day (or per `freq` intraday)."""

    def daily_bars(self, symbols: Sequence[str], start: date, end: date) -> pd.DataFrame:
        return _bars(symbols, pd.bdate_range(start, end, tz="UTC"))

    def intraday_bars(
        self, symbols: Sequence[str], start: datetime, end: datetime, freq: str
    ) -> pd.DataFrame:
        return _bars(symbols, pd.date_range(start, end, freq=freq))

    def quotes(self, symbols: Sequence[str], start: datetime, end: datetime) -> pd.DataFrame:
        rows = pd.MultiIndex.from_product([pd.date_range(start, end, freq="1min"), list(symbols)])
        return pd.DataFrame(1.0, index=rows, columns=list(QUOTE_COLUMNS))


class EqualWeightAgent:
    """Ignores the state and returns equal weights over `n_assets`."""

    def __init__(self, n_assets: int) -> None:
        self.n_assets = n_assets

    def act(self, state: State) -> Action:
        return np.full(self.n_assets, 1.0 / self.n_assets)
