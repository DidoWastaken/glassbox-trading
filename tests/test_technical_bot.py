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


def test_buy_in_uptrend(bot):
    # Sull'ultima barra la SMA veloce e' sopra la lenta (trend rialzista) -> ingresso.
    decline = [100, 99, 98, 97, 96, 95, 94, 93]
    rally = [96, 100]
    history = _make_history(decline + rally)
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)

    assert signal.action == Action.BUY
    assert signal.quantity > 0
    assert "trend rialzista" in signal.explanation
    assert "BTC/USDT" in signal.explanation


def test_buy_in_uptrend_even_if_overbought(bot):
    # Trend forte: l'RSI e' sopra la soglia di ipercomprato, ma si entra lo stesso.
    # Filtrare qui escluderebbe proprio i trend migliori (errore corretto).
    decline = [100, 99, 98, 97, 96, 95, 94, 93]
    rally = [96, 100]
    history = _make_history(decline + rally)
    from src.bots.indicators import rsi
    assert rsi(history["close"], 3).iloc[-1] > bot.rsi_overbought  # davvero ipercomprato
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)
    assert signal.action == Action.BUY


def test_stay_long_while_uptrend(bot):
    # In posizione e trend ancora rialzista: si tiene (non si esce per ipercomprato).
    rally = [90, 94, 98, 102, 106, 110, 114, 118, 122, 126]
    history = _make_history(rally)
    ctx = MarketContext("BTC/USDT", history, cash=5_000.0, position_qty=2.0, position_avg_price=100.0)
    signal = bot.on_data(ctx)
    assert signal.action == Action.HOLD
    assert "trend ancora rialzista" in signal.explanation


def test_sell_when_trend_ends(bot):
    # Dopo un rialzo, il prezzo cade: la SMA veloce scende sotto la lenta -> uscita.
    rally = [90, 94, 98, 102, 106, 110, 114, 118]
    decline = [114, 105, 95]
    history = _make_history(rally + decline)
    ctx = MarketContext("BTC/USDT", history, cash=5_000.0, position_qty=2.0, position_avg_price=100.0)
    signal = bot.on_data(ctx)

    assert signal.action == Action.SELL
    assert signal.quantity == pytest.approx(2.0)
    assert "trend finito" in signal.explanation


def test_no_buy_in_downtrend(bot):
    # Flat e trend ribassista (SMA veloce sotto la lenta): si resta fuori. E' il
    # comportamento che protegge dai mercati in calo.
    rally = [90, 94, 98, 102, 106, 110, 114, 118]
    decline = [114, 105, 95]
    history = _make_history(rally + decline)
    ctx = MarketContext("BTC/USDT", history, cash=5_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)

    assert signal.action == Action.HOLD


def test_buy_quantity_uses_buy_fraction():
    bot = TechnicalBot(fast_period=3, slow_period=5, rsi_period=3, buy_fraction=0.5)
    decline = [100, 99, 98, 97, 96, 95, 94, 93]
    rally = [96, 100]
    history = _make_history(decline + rally)
    ctx = MarketContext("BTC/USDT", history, cash=1_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)

    assert signal.action == Action.BUY
    expected_qty = (1_000.0 * 0.5) / history["close"].iloc[-1]
    assert signal.quantity == pytest.approx(expected_qty)
