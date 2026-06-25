"""Backtest runner: collega Data Layer, Strategy Layer e Simulation Engine.

Itera nel tempo su dati storici, chiede a ogni bot un segnale per ogni
symbol vedendo solo il passato (compresa la barra corrente), esegue gli
ordini sul Paper Broker e salva l'equity. Stesso engine del live mode
(§4.3 della spec): qui cambia solo da dove arrivano i prezzi.

Asset di mercati diversi (crypto 24/7 vs azioni in orario di mercato) non
condividono gli stessi timestamp, e a timeframe intraday nemmeno lo stesso
minuto. Per questo si itera sull'**unione** dei timestamp normalizzati a
UTC: a ogni istante ogni symbol viene valutato col suo ultimo prezzo noto
(`asof`), e un bot agisce su un asset solo quando quell'asset ha davvero
una barra nuova — niente barre sintetiche che falserebbero gli indicatori.
"""

from __future__ import annotations

import pandas as pd

from src.bots.base import Action, Bot, MarketContext

from .broker import OrderError, PaperBroker, Side


def _to_utc(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizza l'indice temporale a UTC tz-aware, cosi' symbol di fonti diverse sono allineabili."""
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    out = df.copy()
    out.index = idx
    return out.sort_index()


def run_backtest(broker: PaperBroker, bots: dict[str, Bot], histories: dict[str, pd.DataFrame]) -> None:
    """Esegue il backtest in-place: ogni operazione e snapshot di equity finiscono su SQLite via broker.

    `histories` deve avere una entry per ogni symbol con un DataFrame OHLCV
    indicizzato per timestamp. Si itera sull'unione dei timestamp di tutti i
    symbol, valutando ciascuno col suo ultimo prezzo disponibile.
    """
    symbols = list(histories.keys())
    if not symbols:
        raise ValueError("nessun symbol fornito al backtest")

    histories = {symbol: _to_utc(df) for symbol, df in histories.items()}
    symbol_times = {symbol: set(df.index) for symbol, df in histories.items()}

    union_index = histories[symbols[0]].index
    for symbol in symbols[1:]:
        union_index = union_index.union(histories[symbol].index)
    union_index = union_index.sort_values()

    if union_index.empty:
        raise ValueError("nessun dato fornito al backtest")

    closes = {symbol: df["close"] for symbol, df in histories.items()}

    for ts in union_index:
        # Prezzo corrente di ogni symbol = ultima chiusura nota a quell'istante (NaN se il
        # symbol non ha ancora dati). Serve sia per eseguire ordini sia per valutare l'equity.
        current_prices: dict[str, float] = {}
        for symbol in symbols:
            price = closes[symbol].asof(ts)
            if pd.notna(price):
                current_prices[symbol] = float(price)

        timestamp = ts.to_pydatetime()

        for bot_name, bot in bots.items():
            for symbol in symbols:
                # Il bot agisce su questo symbol solo se proprio ora e' arrivata una sua barra nuova.
                if ts not in symbol_times[symbol]:
                    continue

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
