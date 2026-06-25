"""Metriche di performance per confrontare i bot.

Calcolate da `trades` ed `equity_history` (§4.5 della spec). Pensate per
essere estendibili: aggiungere una metrica custom significa aggiungere
una funzione qui e una entry in `compute_metrics`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def total_return_pct(equity: pd.Series, initial_capital: float) -> float:
    if equity.empty or initial_capital <= 0:
        return 0.0
    final_equity = equity.iloc[-1]
    return (final_equity / initial_capital - 1) * 100


def sharpe_ratio(equity: pd.Series, periods_per_year: float, risk_free_rate: float = 0.0) -> float:
    """Sharpe ratio annualizzato sui rendimenti periodali dell'equity curve."""
    returns = equity.pct_change().dropna()
    if len(returns) < 2 or returns.std() == 0:
        return 0.0
    excess = returns - (risk_free_rate / periods_per_year)
    return float(excess.mean() / returns.std() * np.sqrt(periods_per_year))


def max_drawdown_pct(equity: pd.Series) -> float:
    """Massima perdita percentuale da un picco precedente (numero negativo, 0 = nessun drawdown)."""
    if equity.empty:
        return 0.0
    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    return float(drawdown.min() * 100)


def trade_pnls(trades: pd.DataFrame) -> pd.Series:
    """P/L realizzato di ogni operazione di chiusura (SELL), per simbolo, a costo medio ponderato.

    Ricostruisce lo stesso criterio del Paper Broker (costo medio) a partire
    dallo storico trades, indipendentemente dallo stato corrente del bot.
    """
    if trades.empty:
        return pd.Series(dtype=float)

    pnls: list[float] = []
    positions: dict[str, tuple[float, float]] = {}  # symbol -> (quantity, avg_price)

    for _, row in trades.sort_values("timestamp").iterrows():
        symbol = row["symbol"]
        qty, avg_price = positions.get(symbol, (0.0, 0.0))

        if row["side"] == "buy":
            new_qty = qty + row["quantity"]
            new_avg = (avg_price * qty + row["price"] * row["quantity"]) / new_qty if new_qty else 0.0
            positions[symbol] = (new_qty, new_avg)
        else:
            pnl = (row["price"] - avg_price) * row["quantity"] - row["fee"]
            pnls.append(pnl)
            remaining = qty - row["quantity"]
            positions[symbol] = (remaining, avg_price if remaining > 0 else 0.0)

    return pd.Series(pnls, dtype=float)


def win_rate_pct(trades: pd.DataFrame) -> float:
    pnls = trade_pnls(trades)
    if pnls.empty:
        return 0.0
    return float((pnls > 0).mean() * 100)


def compute_metrics(
    equity: pd.Series,
    trades: pd.DataFrame,
    initial_capital: float,
    periods_per_year: float,
) -> dict[str, float]:
    """Aggrega tutte le metriche standard in un unico dizionario."""
    return {
        "total_return_pct": total_return_pct(equity, initial_capital),
        "sharpe_ratio": sharpe_ratio(equity, periods_per_year),
        "max_drawdown_pct": max_drawdown_pct(equity),
        "win_rate_pct": win_rate_pct(trades),
        "num_trades": int(len(trades)),
    }
