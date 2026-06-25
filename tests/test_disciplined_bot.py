"""Test del Bot 3 'Il Disciplinato' (risk management) su serie sintetiche."""

from __future__ import annotations

import pandas as pd
import pytest

from src.bots.base import Action, MarketContext
from src.bots.disciplined import DisciplinedBot


def _make_history(opens, highs, lows, closes) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=len(closes), freq="h")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [1000.0] * len(closes)},
        index=index,
    )


def _flat_then_breakout(flat_price: float, breakout_close: float, flat_bars: int = 5) -> pd.DataFrame:
    closes = [flat_price] * flat_bars + [breakout_close]
    highs = [flat_price] * flat_bars + [breakout_close]
    lows = [flat_price - 1] * flat_bars + [breakout_close - 1]
    opens = closes
    return _make_history(opens, highs, lows, closes)


@pytest.fixture
def bot():
    return DisciplinedBot(
        breakout_period=5,
        risk_per_trade_pct=0.01,
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        max_exposure_pct=0.3,
    )


def test_hold_when_insufficient_data(bot):
    history = _make_history([100, 100], [100, 100], [99, 99], [100, 100])
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)
    assert signal.action == Action.HOLD
    assert "dati insufficienti" in signal.explanation


def test_hold_when_no_breakout(bot):
    history = _flat_then_breakout(flat_price=100, breakout_close=100)
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)
    assert signal.action == Action.HOLD
    assert "nessun breakout" in signal.explanation


def test_buy_sized_by_exposure_cap(bot):
    history = _flat_then_breakout(flat_price=100, breakout_close=105)
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)

    assert signal.action == Action.BUY
    expected_qty = (10_000.0 * 0.3) / 105.0
    assert signal.quantity == pytest.approx(expected_qty)
    assert "esposizione massima" in signal.explanation


def test_buy_sized_by_risk_per_trade():
    bot = DisciplinedBot(
        breakout_period=5, risk_per_trade_pct=0.01, stop_loss_pct=0.02, take_profit_pct=0.04, max_exposure_pct=1.0
    )
    history = _flat_then_breakout(flat_price=100, breakout_close=105)
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)

    assert signal.action == Action.BUY
    expected_qty = (10_000.0 * 0.01) / (105.0 * 0.02)
    assert signal.quantity == pytest.approx(expected_qty)
    assert "rischio per trade" in signal.explanation


def test_stop_loss_triggers_sell(bot):
    history = _make_history(
        opens=[100, 100, 100, 100, 100, 100],
        highs=[100, 100, 100, 100, 100, 99],
        lows=[99, 99, 99, 99, 99, 97],
        closes=[100, 100, 100, 100, 100, 98],
    )
    ctx = MarketContext("BTC/USDT", history, cash=5_000.0, position_qty=2.0, position_avg_price=100.0)
    signal = bot.on_data(ctx)

    assert signal.action == Action.SELL
    assert signal.quantity == pytest.approx(2.0)
    assert "stop-loss" in signal.explanation


def test_take_profit_triggers_sell(bot):
    history = _make_history(
        opens=[100, 100, 100, 100, 100, 100],
        highs=[100, 100, 100, 100, 100, 105],
        lows=[99, 99, 99, 99, 99, 99],
        closes=[100, 100, 100, 100, 100, 104],
    )
    ctx = MarketContext("BTC/USDT", history, cash=5_000.0, position_qty=2.0, position_avg_price=100.0)
    signal = bot.on_data(ctx)

    assert signal.action == Action.SELL
    assert signal.quantity == pytest.approx(2.0)
    assert "take-profit" in signal.explanation


def test_hold_open_position_without_stop_or_target(bot):
    history = _make_history(
        opens=[100, 100, 100, 100, 100, 100],
        highs=[100, 100, 100, 100, 100, 102],
        lows=[99, 99, 99, 99, 99, 99],
        closes=[100, 100, 100, 100, 100, 101],
    )
    ctx = MarketContext("BTC/USDT", history, cash=5_000.0, position_qty=2.0, position_avg_price=100.0)
    signal = bot.on_data(ctx)

    assert signal.action == Action.HOLD
    assert "posizione aperta" in signal.explanation
