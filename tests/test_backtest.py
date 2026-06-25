"""Test del backtest runner: collega Data simulati + Bot + Engine + Persistence."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.bots.technical import TechnicalBot
from src.engine.backtest import run_backtest
from src.engine.broker import PaperBroker
from src.persistence.db import init_db
from src.persistence.repository import start_session


def _trend_history(n_bars: int, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-01", periods=n_bars, freq="h")
    close = 100 + np.cumsum(rng.normal(0.05, 1.0, n_bars))
    close = np.clip(close, 1, None)
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": rng.uniform(100, 1000, n_bars),
        },
        index=index,
    )


def test_backtest_populates_trades_and_equity(tmp_path):
    db_path = tmp_path / "glassbox_backtest.db"
    conn = init_db(db_path)
    session_id = start_session(
        conn, mode="backtest", initial_capital=10_000.0, timeframe="1h", fee_pct=0.001, slippage_pct=0.0005
    )
    broker = PaperBroker(conn, session_id, fee_pct=0.001, slippage_pct=0.0005)
    bot = TechnicalBot(fast_period=3, slow_period=5, rsi_period=3, buy_fraction=0.5)
    broker.register_bot(bot.name, initial_capital=10_000.0)

    histories = {"BTC/USDT": _trend_history(60)}
    run_backtest(broker, {bot.name: bot}, histories)

    equity_rows = conn.execute(
        "SELECT COUNT(*) FROM equity_history WHERE bot_name = ?", (bot.name,)
    ).fetchone()[0]
    assert equity_rows == 60  # uno snapshot per ogni barra comune

    state = broker.state(bot.name)
    assert state.cash >= 0


def test_backtest_requires_common_timestamps(tmp_path):
    db_path = tmp_path / "glassbox_backtest2.db"
    conn = init_db(db_path)
    session_id = start_session(
        conn, mode="backtest", initial_capital=10_000.0, timeframe="1h", fee_pct=0.0, slippage_pct=0.0
    )
    broker = PaperBroker(conn, session_id, fee_pct=0.0, slippage_pct=0.0)
    bot = TechnicalBot(fast_period=3, slow_period=5, rsi_period=3)
    broker.register_bot(bot.name, initial_capital=10_000.0)

    h1 = _trend_history(20, seed=1)
    h2 = h1.copy()
    h2.index = h2.index + pd.Timedelta(days=365)  # nessun timestamp in comune

    try:
        run_backtest(broker, {bot.name: bot}, {"A": h1, "B": h2})
        assert False, "doveva sollevare ValueError"
    except ValueError as exc:
        assert "comune" in str(exc)
