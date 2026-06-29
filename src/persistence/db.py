"""Schema SQLite e inizializzazione del database GlassBox."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL CHECK (mode IN ('backtest', 'live')),
    initial_capital REAL NOT NULL,
    timeframe TEXT NOT NULL,
    fee_pct REAL NOT NULL,
    slippage_pct REAL NOT NULL,
    started_at TEXT NOT NULL,
    closed_at TEXT,
    resume_point TEXT
);

CREATE TABLE IF NOT EXISTS bots (
    name TEXT NOT NULL,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    initial_capital REAL NOT NULL,
    cash REAL NOT NULL,
    realized_pnl REAL NOT NULL DEFAULT 0,
    fees_paid REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (name, session_id)
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_name TEXT NOT NULL,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_price REAL NOT NULL,
    UNIQUE (bot_name, session_id, symbol)
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    bot_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    fee REAL NOT NULL,
    explanation TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS equity_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    bot_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    equity REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_bot ON trades(session_id, bot_name);
CREATE INDEX IF NOT EXISTS idx_equity_bot ON equity_history(session_id, bot_name);
"""


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    # check_same_thread=False: Streamlit ri-esegue lo script in thread diversi a ogni
    # interazione, ma la connessione viene riusata tra un rerun e l'altro (salvata in
    # session_state). I rerun sono sequenziali, quindi non c'e' accesso concorrente reale.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Il backtest fa molti piccoli commit (un trade/equity per barra). In modalita' di
    # default ogni commit fa un fsync su disco: e' il collo di bottiglia principale.
    # WAL + synchronous=NORMAL rende questi commit molto piu' economici mantenendo
    # l'integrita' del database (no corruzione in caso di crash dell'app).
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db(db_path: str | Path) -> sqlite3.Connection:
    """Crea (se necessario) le tabelle e ritorna una connessione pronta all'uso."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
