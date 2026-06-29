"""Test del Bot 3 'Il Disciplinato' (risk management) su serie sintetiche.

Uscita: trailing stop (lo stop segue il massimo raggiunto) invece di un
take-profit fisso, per lasciar correre i vincitori. Entrata filtrata dal trend.
"""

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
    # trend_filter_period=0 per isolare la logica di breakout/uscita nei test che non
    # riguardano il filtro di trend (che ha un test dedicato).
    return DisciplinedBot(
        breakout_period=5, risk_per_trade_pct=0.01, stop_loss_pct=0.02,
        max_exposure_pct=0.3, trend_filter_period=0,
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
        breakout_period=5, risk_per_trade_pct=0.01, stop_loss_pct=0.02,
        max_exposure_pct=1.0, trend_filter_period=0,
    )
    history = _flat_then_breakout(flat_price=100, breakout_close=105)
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)

    assert signal.action == Action.BUY
    expected_qty = (10_000.0 * 0.01) / (105.0 * 0.02)
    assert signal.quantity == pytest.approx(expected_qty)
    assert "rischio per trade" in signal.explanation


def test_trend_filter_blocks_entry_in_downtrend():
    # 60 barre in calo: il prezzo finale e' sotto la sua SMA50 -> niente ingressi.
    closes = [200 - i for i in range(60)]
    history = _make_history(closes, [c + 1 for c in closes], [c - 1 for c in closes], closes)
    bot = DisciplinedBot(breakout_period=5, trend_filter_period=50)
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)
    assert signal.action == Action.HOLD
    assert "ribassista" in signal.explanation


def test_trailing_stop_triggers_sell(bot):
    history = _make_history(
        opens=[100, 100, 100, 100, 100, 100],
        highs=[100, 100, 100, 100, 100, 99],
        lows=[99, 99, 99, 99, 99, 97],
        closes=[100, 100, 100, 100, 100, 98],
    )
    # peak parte dal prezzo di carico (100); trailing stop a 98. Il minimo 97 lo colpisce.
    ctx = MarketContext("BTC/USDT", history, cash=5_000.0, position_qty=2.0, position_avg_price=100.0)
    signal = bot.on_data(ctx)

    assert signal.action == Action.SELL
    assert signal.quantity == pytest.approx(2.0)
    assert "trailing stop" in signal.explanation


def _last_bar_history(high: float, low: float) -> pd.DataFrame:
    # 6 barre piatte di riempimento (servono per superare il gate breakout_period+1);
    # solo l'ultima barra conta per la gestione della posizione.
    pad = [100.0] * 5
    return _make_history(pad + [high], pad + [high], pad + [low], pad + [(high + low) / 2])


def test_trailing_stop_ratchets_up_with_price(bot):
    # Barra 1: stop iniziale = 100*0.98 = 98; il minimo 112 lo supera -> HOLD. Dopo, il
    # picco sale a 120 (massimo della barra), quindi alla prossima barra lo stop sara' 117.6.
    ctx1 = MarketContext("BTC/USDT", _last_bar_history(120, 112), cash=5_000.0, position_qty=2.0, position_avg_price=100.0)
    s1 = bot.on_data(ctx1)
    assert s1.action == Action.HOLD

    # Barra 2: stop ora a 117.6 (dal picco 120); il minimo 118 resta sopra -> il vincitore corre.
    ctx2 = MarketContext("BTC/USDT", _last_bar_history(119, 118), cash=5_000.0, position_qty=2.0, position_avg_price=100.0)
    s2 = bot.on_data(ctx2)
    assert s2.action == Action.HOLD

    # Barra 3: il minimo 115 scende sotto lo stop 117.6 -> esce, bloccando un guadagno.
    ctx3 = MarketContext("BTC/USDT", _last_bar_history(117, 115), cash=5_000.0, position_qty=2.0, position_avg_price=100.0)
    s3 = bot.on_data(ctx3)
    assert s3.action == Action.SELL
    assert "trailing stop" in s3.explanation


def test_hold_open_position_above_trailing_stop(bot):
    history = _make_history(
        opens=[100, 100, 100, 100, 100, 100],
        highs=[100, 100, 100, 100, 100, 102],
        lows=[99, 99, 99, 99, 99, 101],
        closes=[100, 100, 100, 100, 100, 101],
    )
    # peak 102, trailing 99.96; il minimo 101 resta sopra -> posizione mantenuta.
    ctx = MarketContext("BTC/USDT", history, cash=5_000.0, position_qty=2.0, position_avg_price=100.0)
    signal = bot.on_data(ctx)

    assert signal.action == Action.HOLD
    assert "posizione aperta" in signal.explanation
