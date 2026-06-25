"""Test del Simulation Engine (Paper Broker) — Fase 1 della spec.

Caso guida: "compro a 100, vendo a 110 -> P/L corretto al netto di fee".
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.engine.broker import OrderError, PaperBroker, Side
from src.persistence.db import init_db
from src.persistence.repository import start_session


@pytest.fixture
def broker(tmp_path):
    db_path = tmp_path / "glassbox_test.db"
    conn = init_db(db_path)
    session_id = start_session(
        conn, mode="backtest", initial_capital=10_000.0, timeframe="1h", fee_pct=0.0, slippage_pct=0.0
    )
    b = PaperBroker(conn, session_id, fee_pct=0.0, slippage_pct=0.0)
    b.register_bot("test_bot", initial_capital=10_000.0)
    return b


def test_buy_then_sell_no_fee_no_slippage(broker):
    ts = datetime.now(timezone.utc)
    broker.execute_order("test_bot", "BTC/USDT", Side.BUY, 1.0, 100.0, ts, "buy test")
    broker.execute_order("test_bot", "BTC/USDT", Side.SELL, 1.0, 110.0, ts, "sell test")

    state = broker.state("test_bot")
    assert state.cash == pytest.approx(10_000.0 + 10.0)
    assert state.realized_pnl == pytest.approx(10.0)
    assert state.fees_paid == pytest.approx(0.0)
    assert "BTC/USDT" not in state.positions


def test_buy_then_sell_with_fee(tmp_path):
    db_path = tmp_path / "glassbox_test_fee.db"
    conn = init_db(db_path)
    session_id = start_session(
        conn, mode="backtest", initial_capital=10_000.0, timeframe="1h", fee_pct=0.01, slippage_pct=0.0
    )
    b = PaperBroker(conn, session_id, fee_pct=0.01, slippage_pct=0.0)
    b.register_bot("test_bot", initial_capital=10_000.0)
    ts = datetime.now(timezone.utc)

    b.execute_order("test_bot", "BTC/USDT", Side.BUY, 1.0, 100.0, ts, "buy")
    b.execute_order("test_bot", "BTC/USDT", Side.SELL, 1.0, 110.0, ts, "sell")

    state = b.state("test_bot")
    buy_fee = 100.0 * 0.01
    sell_fee = 110.0 * 0.01
    expected_cash = 10_000.0 - (100.0 + buy_fee) + (110.0 - sell_fee)
    assert state.cash == pytest.approx(expected_cash)
    assert state.fees_paid == pytest.approx(buy_fee + sell_fee)
    expected_pnl = (110.0 - 100.0) * 1.0 - sell_fee
    assert state.realized_pnl == pytest.approx(expected_pnl)


def test_slippage_worsens_fill_price(tmp_path):
    db_path = tmp_path / "glassbox_test_slip.db"
    conn = init_db(db_path)
    session_id = start_session(
        conn, mode="backtest", initial_capital=10_000.0, timeframe="1h", fee_pct=0.0, slippage_pct=0.01
    )
    b = PaperBroker(conn, session_id, fee_pct=0.0, slippage_pct=0.01)
    b.register_bot("test_bot", initial_capital=10_000.0)
    ts = datetime.now(timezone.utc)

    buy_fill = b.execute_order("test_bot", "BTC/USDT", Side.BUY, 1.0, 100.0, ts, "buy")
    assert buy_fill == pytest.approx(101.0)

    sell_fill = b.execute_order("test_bot", "BTC/USDT", Side.SELL, 1.0, 100.0, ts, "sell")
    assert sell_fill == pytest.approx(99.0)


def test_insufficient_cash_raises(broker):
    ts = datetime.now(timezone.utc)
    with pytest.raises(OrderError):
        broker.execute_order("test_bot", "BTC/USDT", Side.BUY, 1000.0, 100.0, ts, "too big")


def test_insufficient_position_raises(broker):
    ts = datetime.now(timezone.utc)
    with pytest.raises(OrderError):
        broker.execute_order("test_bot", "BTC/USDT", Side.SELL, 1.0, 100.0, ts, "no position")


def test_equity_reflects_open_position(broker):
    ts = datetime.now(timezone.utc)
    broker.execute_order("test_bot", "BTC/USDT", Side.BUY, 2.0, 100.0, ts, "buy")
    equity = broker.equity("test_bot", {"BTC/USDT": 120.0})
    assert equity == pytest.approx((10_000.0 - 200.0) + 2.0 * 120.0)
