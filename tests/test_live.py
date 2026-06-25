"""Test del Live mode: ripresa Opzione B e polling sui prezzi correnti."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src.bots.technical import TechnicalBot
from src.data.source import Bar, DataSource
from src.engine.broker import PaperBroker, Side
from src.engine.live import LiveRunner, start_live_session
from src.persistence.db import init_db
from src.persistence.repository import close_session


class FakeDataSource(DataSource):
    """DataSource finta e deterministica per i test, niente rete."""

    def __init__(self, history: pd.DataFrame, next_bar: Bar):
        self._history = history
        self._next_bar = next_bar

    def get_historical(self, symbol, start, end, timeframe) -> pd.DataFrame:
        return self._history

    def get_latest(self, symbol) -> Bar:
        return self._next_bar


@pytest.fixture
def conn(tmp_path):
    return init_db(tmp_path / "glassbox_live.db")


def test_no_resume_on_first_live_session(conn):
    session_id, broker, resumed = start_live_session(
        conn, ["Il Tecnico"], initial_capital=10_000.0, timeframe="1h", fee_pct=0.0, slippage_pct=0.0
    )
    assert resumed == []
    assert broker.state("Il Tecnico").cash == 10_000.0


def test_resume_carries_forward_cash_and_positions(conn):
    session_id, broker, _ = start_live_session(
        conn, ["Il Tecnico"], initial_capital=10_000.0, timeframe="1h", fee_pct=0.0, slippage_pct=0.0
    )
    ts = datetime.now(timezone.utc)
    broker.execute_order("Il Tecnico", "BTC/USDT", Side.BUY, 1.0, 100.0, ts, "buy di prova")
    close_session(conn, session_id, resume_point="fine sessione 1")

    session_id_2, broker_2, resumed = start_live_session(
        conn, ["Il Tecnico"], initial_capital=10_000.0, timeframe="1h", fee_pct=0.0, slippage_pct=0.0
    )
    assert resumed == ["Il Tecnico"]
    state = broker_2.state("Il Tecnico")
    assert state.cash == pytest.approx(9_900.0)
    assert state.positions["BTC/USDT"].quantity == pytest.approx(1.0)
    assert session_id_2 != session_id


def _make_history(closes: list[float]) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=len(closes), freq="h")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": [1000.0] * len(closes)},
        index=index,
    )


def test_poll_once_executes_signal_on_new_bar(conn):
    decline = [100, 99, 98, 97, 96, 95, 94, 93]
    bootstrap_history = _make_history(decline + [96])  # 9 barre, indice 0..8
    next_timestamp = bootstrap_history.index[-1] + timedelta(hours=1)
    next_bar = Bar(timestamp=next_timestamp.to_pydatetime(), open=100, high=100, low=100, close=100, volume=1000.0)

    source = FakeDataSource(bootstrap_history, next_bar)
    bot = TechnicalBot(fast_period=3, slow_period=5, rsi_period=3, rsi_overbought=99)

    session_id, broker, _ = start_live_session(
        conn, [bot.name], initial_capital=10_000.0, timeframe="1h", fee_pct=0.0, slippage_pct=0.0
    )
    runner = LiveRunner(broker, {bot.name: bot}, {"BTC/USDT": source})
    runner.histories["BTC/USDT"] = bootstrap_history

    runner.poll_once()

    trades = conn.execute(
        "SELECT * FROM trades WHERE session_id = ? AND bot_name = ?", (session_id, bot.name)
    ).fetchall()
    assert len(trades) == 1
    assert trades[0]["side"] == "buy"

    equity_rows = conn.execute(
        "SELECT * FROM equity_history WHERE session_id = ? AND bot_name = ?", (session_id, bot.name)
    ).fetchall()
    assert len(equity_rows) == 1


def test_poll_once_skips_when_no_new_bar(conn):
    decline = [100, 99, 98, 97, 96, 95, 94, 93]
    bootstrap_history = _make_history(decline + [96])
    stale_bar = Bar(
        timestamp=bootstrap_history.index[-1].to_pydatetime(),  # stesso timestamp, niente di nuovo
        open=96, high=96, low=96, close=96, volume=1000.0,
    )
    source = FakeDataSource(bootstrap_history, stale_bar)
    bot = TechnicalBot(fast_period=3, slow_period=5, rsi_period=3)

    session_id, broker, _ = start_live_session(
        conn, [bot.name], initial_capital=10_000.0, timeframe="1h", fee_pct=0.0, slippage_pct=0.0
    )
    runner = LiveRunner(broker, {bot.name: bot}, {"BTC/USDT": source})
    runner.histories["BTC/USDT"] = bootstrap_history

    runner.poll_once()

    trades = conn.execute("SELECT * FROM trades WHERE session_id = ?", (session_id,)).fetchall()
    assert len(trades) == 0
