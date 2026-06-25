"""Funzioni di lettura/scrittura dello stato su SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float


@dataclass
class BotState:
    name: str
    initial_capital: float
    cash: float
    realized_pnl: float
    fees_paid: float
    positions: dict[str, Position]


def start_session(
    conn: sqlite3.Connection,
    mode: str,
    initial_capital: float,
    timeframe: str,
    fee_pct: float,
    slippage_pct: float,
) -> int:
    cur = conn.execute(
        """INSERT INTO sessions (mode, initial_capital, timeframe, fee_pct, slippage_pct, started_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (mode, initial_capital, timeframe, fee_pct, slippage_pct, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def close_session(conn: sqlite3.Connection, session_id: int, resume_point: str | None = None) -> None:
    conn.execute(
        "UPDATE sessions SET closed_at = ?, resume_point = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), resume_point, session_id),
    )
    conn.commit()


def register_bot(conn: sqlite3.Connection, session_id: int, bot_name: str, initial_capital: float) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO bots (name, session_id, initial_capital, cash, realized_pnl, fees_paid)
           VALUES (?, ?, ?, ?, 0, 0)""",
        (bot_name, session_id, initial_capital, initial_capital),
    )
    conn.commit()


def load_bot_state(conn: sqlite3.Connection, session_id: int, bot_name: str) -> BotState:
    row = conn.execute(
        "SELECT * FROM bots WHERE name = ? AND session_id = ?", (bot_name, session_id)
    ).fetchone()
    if row is None:
        raise ValueError(f"bot non trovato: {bot_name} (session {session_id})")

    pos_rows = conn.execute(
        "SELECT symbol, quantity, avg_price FROM positions WHERE bot_name = ? AND session_id = ?",
        (bot_name, session_id),
    ).fetchall()
    positions = {r["symbol"]: Position(r["symbol"], r["quantity"], r["avg_price"]) for r in pos_rows}

    return BotState(
        name=row["name"],
        initial_capital=row["initial_capital"],
        cash=row["cash"],
        realized_pnl=row["realized_pnl"],
        fees_paid=row["fees_paid"],
        positions=positions,
    )


def save_bot_state(conn: sqlite3.Connection, session_id: int, state: BotState) -> None:
    conn.execute(
        """UPDATE bots SET cash = ?, realized_pnl = ?, fees_paid = ?
           WHERE name = ? AND session_id = ?""",
        (state.cash, state.realized_pnl, state.fees_paid, state.name, session_id),
    )
    for pos in state.positions.values():
        if pos.quantity == 0:
            conn.execute(
                "DELETE FROM positions WHERE bot_name = ? AND session_id = ? AND symbol = ?",
                (state.name, session_id, pos.symbol),
            )
        else:
            conn.execute(
                """INSERT INTO positions (bot_name, session_id, symbol, quantity, avg_price)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (bot_name, session_id, symbol)
                   DO UPDATE SET quantity = excluded.quantity, avg_price = excluded.avg_price""",
                (state.name, session_id, pos.symbol, pos.quantity, pos.avg_price),
            )
    conn.commit()


def record_trade(
    conn: sqlite3.Connection,
    session_id: int,
    bot_name: str,
    timestamp: datetime,
    symbol: str,
    side: str,
    price: float,
    quantity: float,
    fee: float,
    explanation: str,
) -> None:
    conn.execute(
        """INSERT INTO trades (session_id, bot_name, timestamp, symbol, side, price, quantity, fee, explanation)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, bot_name, timestamp.isoformat(), symbol, side, price, quantity, fee, explanation),
    )
    conn.commit()


def record_equity(
    conn: sqlite3.Connection, session_id: int, bot_name: str, timestamp: datetime, equity: float
) -> None:
    conn.execute(
        "INSERT INTO equity_history (session_id, bot_name, timestamp, equity) VALUES (?, ?, ?, ?)",
        (session_id, bot_name, timestamp.isoformat(), equity),
    )
    conn.commit()
