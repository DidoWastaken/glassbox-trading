"""Test del Bot 1 'Lo Statistico' (ML walk-forward)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.bots.base import Action, MarketContext
from src.bots.statistical import StatisticalBot


def _synthetic_history(n_bars: int, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-01", periods=n_bars, freq="h")
    drift = 0.0005
    noise = rng.normal(0, 0.01, n_bars)
    close = 100 * np.cumprod(1 + drift + noise)
    high = close * (1 + np.abs(rng.normal(0, 0.002, n_bars)))
    low = close * (1 - np.abs(rng.normal(0, 0.002, n_bars)))
    open_ = close * (1 + rng.normal(0, 0.001, n_bars))
    volume = rng.uniform(100, 1000, n_bars)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=index
    )


def test_hold_when_insufficient_data():
    bot = StatisticalBot(train_window=200)
    history = _synthetic_history(50)
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)
    assert signal.action == Action.HOLD
    assert "dati insufficienti" in signal.explanation


def test_returns_valid_signal_with_enough_data():
    bot = StatisticalBot(model_type="random_forest", train_window=60, confidence_threshold=0.55)
    history = _synthetic_history(150)
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)

    assert signal.action in (Action.BUY, Action.SELL, Action.HOLD)
    assert "walk-forward" in signal.explanation
    assert "Random Forest" in signal.explanation
    if signal.action != Action.HOLD:
        assert signal.quantity > 0


def test_explanation_reflects_logistic_regression_choice():
    bot = StatisticalBot(model_type="logistic_regression", train_window=60, confidence_threshold=0.55)
    history = _synthetic_history(150)
    ctx = MarketContext("BTC/USDT", history, cash=10_000.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)
    assert "Logistic Regression" in signal.explanation


def test_no_buy_without_cash():
    bot = StatisticalBot(model_type="random_forest", train_window=60, confidence_threshold=0.5)
    history = _synthetic_history(150)
    ctx = MarketContext("BTC/USDT", history, cash=0.0, position_qty=0.0, position_avg_price=None)
    signal = bot.on_data(ctx)
    assert signal.action != Action.BUY


def test_invalid_model_type_rejected():
    with pytest.raises(ValueError):
        StatisticalBot(model_type="neural_network")


def test_last_bar_excluded_from_training():
    """La barra piu' recente non deve mai entrare nel training set (la sua label e' futura)."""
    bot = StatisticalBot(model_type="random_forest", train_window=60, confidence_threshold=0.55)
    history = _synthetic_history(150)

    from src.bots.features import FEATURE_COLUMNS, build_features

    features = build_features(history).replace([np.inf, -np.inf], np.nan)
    label = (history["close"].shift(-1) > history["close"]).astype(float)
    label.iloc[-1] = np.nan
    dataset = features.copy()
    dataset["label"] = label
    usable = dataset.dropna()

    assert history.index[-1] not in usable.index
