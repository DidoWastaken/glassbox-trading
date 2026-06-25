"""Test dell'Analytics Layer."""

from __future__ import annotations

import pandas as pd
import pytest

from src.analytics.metrics import (
    compute_metrics,
    max_drawdown_pct,
    sharpe_ratio,
    total_return_pct,
    trade_pnls,
    win_rate_pct,
)


def test_total_return():
    equity = pd.Series([10_000.0, 10_500.0, 11_000.0])
    assert total_return_pct(equity, 10_000.0) == pytest.approx(10.0)


def test_total_return_empty():
    assert total_return_pct(pd.Series(dtype=float), 10_000.0) == 0.0


def test_max_drawdown():
    equity = pd.Series([100.0, 120.0, 90.0, 110.0])
    # picco 120 -> minimo 90 = -25%
    assert max_drawdown_pct(equity) == pytest.approx(-25.0)


def test_max_drawdown_no_loss():
    equity = pd.Series([100.0, 110.0, 120.0])
    assert max_drawdown_pct(equity) == pytest.approx(0.0)


def test_sharpe_ratio_positive_trend():
    equity = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0])
    assert sharpe_ratio(equity, periods_per_year=252) > 0


def test_sharpe_ratio_flat_is_zero():
    equity = pd.Series([100.0, 100.0, 100.0])
    assert sharpe_ratio(equity, periods_per_year=252) == 0.0


def _trades_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_trade_pnls_simple_round_trip():
    trades = _trades_df(
        [
            {"timestamp": "2024-01-01T00:00:00", "symbol": "BTC/USDT", "side": "buy", "price": 100.0, "quantity": 1.0, "fee": 0.0},
            {"timestamp": "2024-01-01T01:00:00", "symbol": "BTC/USDT", "side": "sell", "price": 110.0, "quantity": 1.0, "fee": 1.0},
        ]
    )
    pnls = trade_pnls(trades)
    assert len(pnls) == 1
    assert pnls.iloc[0] == pytest.approx(9.0)  # (110-100)*1 - 1 fee


def test_win_rate_mixed_trades():
    trades = _trades_df(
        [
            {"timestamp": "2024-01-01T00:00:00", "symbol": "BTC/USDT", "side": "buy", "price": 100.0, "quantity": 1.0, "fee": 0.0},
            {"timestamp": "2024-01-01T01:00:00", "symbol": "BTC/USDT", "side": "sell", "price": 110.0, "quantity": 1.0, "fee": 0.0},
            {"timestamp": "2024-01-01T02:00:00", "symbol": "BTC/USDT", "side": "buy", "price": 110.0, "quantity": 1.0, "fee": 0.0},
            {"timestamp": "2024-01-01T03:00:00", "symbol": "BTC/USDT", "side": "sell", "price": 105.0, "quantity": 1.0, "fee": 0.0},
        ]
    )
    assert win_rate_pct(trades) == pytest.approx(50.0)


def test_win_rate_no_trades():
    assert win_rate_pct(pd.DataFrame()) == 0.0


def test_compute_metrics_keys():
    equity = pd.Series([10_000.0, 10_200.0, 9_800.0, 10_500.0])
    trades = _trades_df(
        [
            {"timestamp": "2024-01-01T00:00:00", "symbol": "BTC/USDT", "side": "buy", "price": 100.0, "quantity": 1.0, "fee": 0.0},
            {"timestamp": "2024-01-01T01:00:00", "symbol": "BTC/USDT", "side": "sell", "price": 110.0, "quantity": 1.0, "fee": 0.0},
        ]
    )
    metrics = compute_metrics(equity, trades, initial_capital=10_000.0, periods_per_year=24 * 365)
    assert set(metrics.keys()) == {
        "total_return_pct",
        "sharpe_ratio",
        "max_drawdown_pct",
        "win_rate_pct",
        "num_trades",
    }
    assert metrics["num_trades"] == 2
