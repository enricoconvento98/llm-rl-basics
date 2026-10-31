from datetime import UTC, datetime, timedelta, timezone

import pytest

from rltrading.domain import ChildOrder, Fill, OrderId, OrderType, ParentOrder, Side, TargetWeights

T0 = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)


class TestTargetWeights:
    def test_valid_weights_and_cash(self) -> None:
        tw = TargetWeights(T0, {"SPY": 0.6, "IEF": 0.3})
        assert tw.cash == pytest.approx(0.1)

    def test_fully_invested_has_zero_cash(self) -> None:
        assert TargetWeights(T0, {"SPY": 0.5, "IEF": 0.5}).cash == 0.0

    @pytest.mark.parametrize("weights", [{"SPY": -0.1}, {"SPY": 1.2}, {"SPY": 0.7, "IEF": 0.4}])
    def test_rejects_shorts_and_leverage(self, weights: dict[str, float]) -> None:
        with pytest.raises(ValueError, match="no"):
            TargetWeights(T0, weights)

    def test_weights_are_immutable_copy(self) -> None:
        source = {"SPY": 0.5}
        tw = TargetWeights(T0, source)
        source["SPY"] = 0.9  # mutating the input must not change the validated object
        assert tw.weights["SPY"] == 0.5
        with pytest.raises(TypeError):
            tw.weights["SPY"] = 0.9  # type: ignore[index]

    def test_requires_utc(self) -> None:
        with pytest.raises(ValueError, match="UTC"):
            TargetWeights(datetime(2026, 1, 5), {"SPY": 0.5})  # noqa: DTZ001
        with pytest.raises(ValueError, match="UTC"):
            TargetWeights(datetime(2026, 1, 5, tzinfo=timezone(timedelta(hours=1))), {"SPY": 0.5})


class TestOrders:
    def test_parent_order_deadline_after_creation(self) -> None:
        ParentOrder("SPY", Side.BUY, 10, created_at=T0, deadline=T0 + timedelta(hours=2))
        with pytest.raises(ValueError, match="deadline"):
            ParentOrder("SPY", Side.BUY, 10, created_at=T0, deadline=T0)

    @pytest.mark.parametrize("qty", [0, -5])
    def test_quantities_must_be_positive(self, qty: float) -> None:
        with pytest.raises(ValueError, match="qty"):
            ChildOrder("SPY", Side.SELL, qty, OrderType.MARKET)

    def test_limit_order_needs_price(self) -> None:
        with pytest.raises(ValueError, match="limit_price"):
            ChildOrder("SPY", Side.BUY, 1, OrderType.LIMIT)
        assert ChildOrder("SPY", Side.BUY, 1, OrderType.LIMIT, limit_price=500.0).limit_price == 500.0

    def test_market_order_rejects_price(self) -> None:
        with pytest.raises(ValueError, match="market orders"):
            ChildOrder("SPY", Side.BUY, 1, OrderType.MARKET, limit_price=500.0)

    def test_bad_symbol(self) -> None:
        with pytest.raises(ValueError, match="symbol"):
            ChildOrder(" SPY", Side.BUY, 1, OrderType.MARKET)


class TestFill:
    def test_notional(self) -> None:
        assert Fill(OrderId("1"), "SPY", Side.BUY, 10, 500.0, T0, fees=1.0).notional == 5000.0

    def test_rejects_negative_fees(self) -> None:
        with pytest.raises(ValueError, match="fees"):
            Fill(OrderId("1"), "SPY", Side.BUY, 10, 500.0, T0, fees=-1.0)
