"""The fakes satisfy the interfaces, and the interfaces are usable end to end."""

from datetime import UTC, date, datetime

import numpy as np

from rltrading.agents.base import Agent
from rltrading.broker.base import Broker
from rltrading.data.providers.base import BAR_COLUMNS, DataProvider, QuoteProvider
from rltrading.domain import ChildOrder, OrderType, Side

from .fakes import EqualWeightAgent, FakeBroker, FakeDataProvider


def test_fakes_implement_protocols() -> None:
    assert isinstance(FakeBroker(cash=1000), Broker)
    assert isinstance(FakeDataProvider(), DataProvider)
    assert isinstance(FakeDataProvider(), QuoteProvider)
    assert isinstance(EqualWeightAgent(3), Agent)


def test_objects_missing_methods_do_not_match() -> None:
    assert not isinstance(object(), Broker)
    assert not isinstance(object(), DataProvider)


def test_daily_bars_schema() -> None:
    bars = FakeDataProvider().daily_bars(["SPY", "IEF"], date(2026, 1, 5), date(2026, 1, 9))
    assert list(bars.columns) == list(BAR_COLUMNS)
    assert bars.index.names == ["timestamp", "symbol"]
    assert len(bars) == 5 * 2


def test_broker_roundtrip() -> None:
    start = datetime.now(UTC)
    broker: Broker = FakeBroker(cash=10_000, price=100.0)
    broker.place_order(ChildOrder("SPY", Side.BUY, 10, OrderType.MARKET))
    broker.place_order(ChildOrder("SPY", Side.SELL, 4, OrderType.MARKET))
    assert broker.positions() == {"SPY": 6}
    assert broker.cash() == 10_000 - 600
    assert [f.qty for f in broker.fills(since=start)] == [10, 4]


def test_agent_action_shape() -> None:
    action = EqualWeightAgent(4).act(np.zeros(10))
    assert action.shape == (4,)
    assert action.sum() == 1.0
