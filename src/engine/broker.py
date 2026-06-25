"""Simulation Engine — Paper Broker.

Esegue ordini "compra/vendi a prezzo reale" applicando fee e slippage
configurabili, aggiorna il portafoglio di ciascun bot e salva ogni
operazione su SQLite. Stesso engine per backtest e live (§4.3 della spec).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from enum import Enum

from src.persistence.repository import (
    BotState,
    Position,
    load_bot_state,
    record_equity,
    record_trade,
    register_bot,
    save_bot_state,
)


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderError(Exception):
    """Ordine non eseguibile (es. cassa insufficiente, posizione insufficiente)."""


class PaperBroker:
    """Broker simulato: un'istanza per sessione, condivisa da tutti i bot."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        session_id: int,
        fee_pct: float,
        slippage_pct: float,
    ):
        self.conn = conn
        self.session_id = session_id
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct
        self._states: dict[str, BotState] = {}

    def register_bot(self, bot_name: str, initial_capital: float) -> None:
        register_bot(self.conn, self.session_id, bot_name, initial_capital)
        self._states[bot_name] = load_bot_state(self.conn, self.session_id, bot_name)

    def _state(self, bot_name: str) -> BotState:
        if bot_name not in self._states:
            self._states[bot_name] = load_bot_state(self.conn, self.session_id, bot_name)
        return self._states[bot_name]

    def execute_order(
        self,
        bot_name: str,
        symbol: str,
        side: Side,
        quantity: float,
        market_price: float,
        timestamp: datetime,
        explanation: str,
    ) -> float:
        """Esegue un ordine market. Ritorna il prezzo di esecuzione effettivo (post-slippage).

        Lo slippage peggiora sempre il prezzo per chi ordina (buy più caro, sell più basso):
        evita il "simulatore troppo gentile" citato nella spec.
        """
        if quantity <= 0:
            raise OrderError("quantity deve essere positiva")
        if market_price <= 0:
            raise OrderError("market_price deve essere positivo")

        state = self._state(bot_name)

        if side == Side.BUY:
            fill_price = market_price * (1 + self.slippage_pct)
        else:
            fill_price = market_price * (1 - self.slippage_pct)

        notional = fill_price * quantity
        fee = notional * self.fee_pct

        if side == Side.BUY:
            total_cost = notional + fee
            if total_cost > state.cash:
                raise OrderError(
                    f"{bot_name}: cassa insufficiente per comprare {quantity} {symbol} "
                    f"(serve {total_cost:.2f}, disponibile {state.cash:.2f})"
                )
            state.cash -= total_cost
            state.fees_paid += fee
            existing = state.positions.get(symbol)
            if existing is None:
                state.positions[symbol] = Position(symbol, quantity, fill_price)
            else:
                new_qty = existing.quantity + quantity
                new_avg = (existing.avg_price * existing.quantity + fill_price * quantity) / new_qty
                state.positions[symbol] = Position(symbol, new_qty, new_avg)
        else:
            existing = state.positions.get(symbol)
            if existing is None or existing.quantity < quantity:
                held = existing.quantity if existing else 0.0
                raise OrderError(
                    f"{bot_name}: posizione insufficiente per vendere {quantity} {symbol} (detenuto {held})"
                )
            proceeds = notional - fee
            state.cash += proceeds
            state.fees_paid += fee
            state.realized_pnl += (fill_price - existing.avg_price) * quantity - fee
            remaining = existing.quantity - quantity
            if remaining == 0:
                del state.positions[symbol]
            else:
                state.positions[symbol] = Position(symbol, remaining, existing.avg_price)

        save_bot_state(self.conn, self.session_id, state)
        record_trade(
            self.conn,
            self.session_id,
            bot_name,
            timestamp,
            symbol,
            side.value,
            fill_price,
            quantity,
            fee,
            explanation,
        )
        return fill_price

    def equity(self, bot_name: str, current_prices: dict[str, float]) -> float:
        """Valore totale del portafoglio: cassa + posizioni valutate ai prezzi correnti."""
        state = self._state(bot_name)
        positions_value = sum(
            pos.quantity * current_prices[symbol]
            for symbol, pos in state.positions.items()
            if symbol in current_prices
        )
        return state.cash + positions_value

    def snapshot_equity(self, bot_name: str, current_prices: dict[str, float], timestamp: datetime) -> float:
        value = self.equity(bot_name, current_prices)
        record_equity(self.conn, self.session_id, bot_name, timestamp, value)
        return value

    def state(self, bot_name: str) -> BotState:
        return self._state(bot_name)
