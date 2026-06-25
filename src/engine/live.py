"""Live mode: paper trading sui prezzi che arrivano in tempo reale.

Stesso Paper Broker del backtest (§4.3 della spec): qui cambia solo la
fonte dei prezzi (dati che arrivano ora invece che storici).

Ripresa **Opzione B** (decisa in spec §3): alla riaccensione l'app ignora
il periodo in cui era spenta e riparte dai prezzi attuali; i portafogli
vengono riportati intatti dall'ultima sessione live (cassa, posizioni,
P/L realizzato, fee pagate), non resettati al capitale iniziale.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.bots.base import Action, Bot, MarketContext
from src.data.source import DataSource
from src.persistence.db import get_connection
from src.persistence.repository import get_previous_live_state, save_bot_state, start_session

from .broker import OrderError, PaperBroker, Side


def start_live_session(
    conn,
    bot_names: list[str],
    initial_capital: float,
    timeframe: str,
    fee_pct: float,
    slippage_pct: float,
) -> tuple[int, PaperBroker, list[str]]:
    """Avvia una nuova sessione live, riportando lo stato dei bot dalla precedente (Opzione B).

    Ritorna (session_id, broker, nomi_bot_ripresi).
    """
    session_id = start_session(
        conn, mode="live", initial_capital=initial_capital, timeframe=timeframe,
        fee_pct=fee_pct, slippage_pct=slippage_pct,
    )
    broker = PaperBroker(conn, session_id, fee_pct=fee_pct, slippage_pct=slippage_pct)
    resumed: list[str] = []

    for bot_name in bot_names:
        # Lo stato precedente va letto PRIMA di registrare il bot per la nuova sessione,
        # altrimenti la riga appena inserita verrebbe scambiata per "la sessione precedente".
        previous = get_previous_live_state(conn, bot_name)
        broker.register_bot(bot_name, initial_capital)
        if previous is not None:
            state = broker.state(bot_name)
            state.cash = previous.cash
            state.realized_pnl = previous.realized_pnl
            state.fees_paid = previous.fees_paid
            state.positions = previous.positions
            save_bot_state(conn, session_id, state)
            resumed.append(bot_name)

    return session_id, broker, resumed


class LiveRunner:
    """Esegue i bot sui prezzi correnti, simbolo per simbolo, sondando le fonti dati."""

    def __init__(self, broker: PaperBroker, bots: dict[str, Bot], data_sources: dict[str, DataSource]):
        self.broker = broker
        self.bots = bots
        self.data_sources = data_sources
        self.histories: dict[str, pd.DataFrame] = {}

    def bootstrap(self, lookback_start: datetime, lookback_end: datetime, timeframe: str) -> None:
        """Carica un po' di storico per ogni symbol, cosi' gli indicatori hanno dati su cui scaldarsi."""
        for symbol, source in self.data_sources.items():
            self.histories[symbol] = source.get_historical(symbol, lookback_start, lookback_end, timeframe)

    def poll_once(self) -> dict[str, float]:
        """Un singolo giro: prende l'ultimo prezzo per ogni symbol, fa decidere i bot, esegue gli ordini.

        Ritorna i prezzi correnti usati in questo giro.
        """
        current_prices: dict[str, float] = {}
        new_bar_symbols: set[str] = set()

        for symbol, source in self.data_sources.items():
            bar = source.get_latest(symbol)
            current_prices[symbol] = bar.close
            history = self.histories.get(symbol)

            is_new_bar = history is None or history.empty or bar.timestamp > history.index[-1]
            if is_new_bar:
                new_row = pd.DataFrame(
                    [[bar.open, bar.high, bar.low, bar.close, bar.volume]],
                    columns=["open", "high", "low", "close", "volume"],
                    index=[pd.Timestamp(bar.timestamp)],
                )
                self.histories[symbol] = pd.concat([history, new_row]) if history is not None else new_row
                new_bar_symbols.add(symbol)

        timestamp = datetime.now(timezone.utc)
        for bot_name, bot in self.bots.items():
            for symbol in self.data_sources:
                if symbol not in new_bar_symbols:
                    continue  # niente di nuovo per questo symbol in questo giro
                history = self.histories[symbol]
                state = self.broker.state(bot_name)
                position = state.positions.get(symbol)

                context = MarketContext(
                    symbol=symbol, history=history, cash=state.cash,
                    position_qty=position.quantity if position else 0.0,
                    position_avg_price=position.avg_price if position else None,
                )
                signal = bot.on_data(context)
                if signal.action == Action.HOLD:
                    continue
                side = Side.BUY if signal.action == Action.BUY else Side.SELL
                try:
                    self.broker.execute_order(
                        bot_name, symbol, side, signal.quantity, current_prices[symbol], timestamp, signal.explanation
                    )
                except OrderError:
                    continue

            self.broker.snapshot_equity(bot_name, current_prices, timestamp)

        return current_prices

    def run(self, poll_interval_seconds: float, max_iterations: int | None = None) -> None:
        """Loop di polling. Ogni `poll_once` salva subito su SQLite (nessun batch in memoria)."""
        iterations = 0
        while max_iterations is None or iterations < max_iterations:
            self.poll_once()
            iterations += 1
            if max_iterations is None or iterations < max_iterations:
                time.sleep(poll_interval_seconds)
