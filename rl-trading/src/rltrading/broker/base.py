"""Broker interface (HANDOFF §5). Backtests, shadow mode and paper trading only differ in which
implementation of this protocol receives the orders."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from rltrading.domain import ChildOrder, Fill, OrderId


@runtime_checkable
class Broker(Protocol):
    def positions(self) -> dict[str, float]:
        """Current quantity held per symbol."""
        ...

    def cash(self) -> float:
        """Available cash in the account's base currency."""
        ...

    def place_order(self, order: ChildOrder) -> OrderId: ...

    def cancel(self, order_id: OrderId) -> None: ...

    def open_orders(self) -> list[OrderId]:
        """Orders placed but not yet filled or cancelled. The kill switch (HANDOFF §6) cancels these."""
        ...

    def fills(self, since: datetime) -> list[Fill]:
        """Fills with timestamp >= `since` (UTC)."""
        ...
