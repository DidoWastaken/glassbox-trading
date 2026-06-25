"""Backtest runner: collega Data Layer, Strategy Layer e Simulation Engine.

Itera barra per barra su dati storici, chiede a ogni bot un segnale per
ogni symbol vedendo solo il passato (compresa la barra corrente), esegue
gli ordini sul Paper Broker e salva l'equity. Stesso engine del live mode
(§4.3 della spec): qui cambia solo da dove arrivano i prezzi.
"""

from __future__ import annotations

import pandas as pd

from src.bots.base import Action, Bot, MarketContext

from .broker import OrderError, PaperBroker, Side


def run_backtest(broker: PaperBroker, bots: dict[str, Bot], histories: dict[str, pd.DataFrame]) -> None:
    """Esegue il backtest in-place: ogni operazione e snapshot di equity finiscono su SQLite via broker.

    `histories` deve avere una entry per ogni symbol con un DataFrame OHLCV
    indicizzato per timestamp. Si itera solo sui timestamp comuni a tutti
    i symbol, per garantire un confronto coerente tra i bot.
    """
    symbols = list(histories.keys())
    if not symbols:
        raise ValueError("nessun symbol fornito al backtest")

    common_index = histories[symbols[0]].index
    for symbol in symbols[1:]:
        common_index = common_index.intersection(histories[symbol].index)
    common_index = common_index.sort_values()

    if common_index.empty:
        raise ValueError("nessun timestamp comune tra i symbol forniti")

    for ts in common_index:
        current_prices = {symbol: float(histories[symbol].loc[ts, "close"]) for symbol in symbols}
        timestamp = ts.to_pydatetime()

        for bot_name, bot in bots.items():
            for symbol in symbols:
                hist_slice = histories[symbol].loc[:ts]
                state = broker.state(bot_name)
                position = state.positions.get(symbol)

                context = MarketContext(
                    symbol=symbol,
                    history=hist_slice,
                    cash=state.cash,
                    position_qty=position.quantity if position else 0.0,
                    position_avg_price=position.avg_price if position else None,
                )
                signal = bot.on_data(context)
                if signal.action == Action.HOLD:
                    continue

                side = Side.BUY if signal.action == Action.BUY else Side.SELL
                try:
                    broker.execute_order(
                        bot_name, symbol, side, signal.quantity, current_prices[symbol], timestamp, signal.explanation
                    )
                except OrderError:
                    continue

            broker.snapshot_equity(bot_name, current_prices, timestamp)
