"""Test del Bot 2 'Il Tecnico' su serie di prezzo sintetiche."""

from __future__ import annotations

import pandas as pd
import pytest

from src.bots.base import Action, MarketContext
from src.bots.technical import TechnicalBot


def _make_history(closes: list[float]) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=len(closes), freq="h")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [1000.0] * len(closes),
        },
        index=index,
    )


@pytest.fixture
def bot():
    return TechnicalBot(fast_period=3, slow_period=5, rsi_period=3, rsi_overbought=70, rsi_oversold=30)


def test_hold_when_insufficient_data(bot):
    history = _make_history([100, 99, 98])
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)
    assert signal.action == Action.HOLD
    assert "dati insufficienti" in signal.explanation


def test_buy_on_golden_cross():
    # RSI filter disattivato (overbought alto) per isolare la sola logica di crossover.
    # Il golden cross (SMA3 supera SMA5) avviene esattamente sull'ultima barra.
    bot = TechnicalBot(fast_period=3, slow_period=5, rsi_period=3, rsi_overbought=99)
    decline = [100, 99, 98, 97, 96, 95, 94, 93]
    rally = [96, 100]
    closes = decline + rally
    history = _make_history(closes)
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)

    assert signal.action == Action.BUY
    assert signal.quantity > 0
    assert "golden cross" in signal.explanation
    assert "BTC/USDT" in signal.explanation


def test_no_buy_when_overbought(bot):
    # Stesso golden cross di test_buy_on_golden_cross, ma con filtro RSI di default (70):
    # il rally e' cosi' rapido che l'RSI sale sopra la soglia, quindi niente BUY.
    decline = [100, 99, 98, 97, 96, 95, 94, 93]
    rally = [96, 100]
    closes = decline + rally
    history = _make_history(closes)
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)

    assert signal.action == Action.HOLD


def test_sell_on_death_cross(bot):
    rally = [90, 94, 98, 102, 106, 110, 114, 118]
    decline = [114, 105, 95]
    closes = rally + decline
    history = _make_history(closes)
    ctx = MarketContext("BTC/USDT", history, cash=5_000.0, position_qty=2.0, position_avg_price=100.0)
    signal = bot.on_data(ctx)

    assert signal.action == Action.SELL
    assert signal.quantity == pytest.approx(2.0)
    assert "death cross" in signal.explanation


def test_no_sell_without_open_position(bot):
    rally = [90, 94, 98, 102, 106, 110, 114, 118]
    decline = [114, 105, 95]
    closes = rally + decline
    history = _make_history(closes)
    ctx = MarketContext("BTC/USDT", history, cash=5_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)

    assert signal.action == Action.HOLD


def test_buy_quantity_uses_buy_fraction():
    bot = TechnicalBot(fast_period=3, slow_period=5, rsi_period=3, rsi_overbought=99, buy_fraction=0.5)
    decline = [100, 99, 98, 97, 96, 95, 94, 93]
    rally = [96, 100]
    history = _make_history(decline + rally)
    ctx = MarketContext("BTC/USDT", history, cash=1_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)

    assert signal.action == Action.BUY
    expected_qty = (1_000.0 * 0.5) / history["close"].iloc[-1]
    assert signal.quantity == pytest.approx(expected_qty)
