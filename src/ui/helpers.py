"""Funzioni di supporto per la GUI Streamlit, separate per essere testabili senza Streamlit."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.bots.base import Bot
from src.bots.disciplined import DisciplinedBot
from src.bots.statistical import StatisticalBot
from src.bots.technical import TechnicalBot
from src.data.ccxt_source import CcxtDataSource
from src.data.source import DataSource
from src.data.yfinance_source import YFinanceDataSource


def is_crypto_symbol(symbol: str) -> bool:
    """Convenzione: i symbol crypto contengono '/' (es. BTC/USDT), le azioni no (es. AAPL)."""
    return "/" in symbol


def get_data_source(symbol: str) -> DataSource:
    return CcxtDataSource() if is_crypto_symbol(symbol) else YFinanceDataSource()


def fetch_histories(symbols: list[str], start: datetime, end: datetime, timeframe: str) -> dict[str, pd.DataFrame]:
    histories: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        source = get_data_source(symbol)
        histories[symbol] = source.get_historical(symbol, start, end, timeframe)
    return histories


def build_default_bots(ml_model: str) -> dict[str, Bot]:
    """Le tre filosofie GlassBox con parametri interni di default ragionevoli.

    I parametri "macro" (capitale, fee, slippage, asset, timeframe) sono
    configurabili dall'utente in GUI; questi sono parametri interni di
    ciascuna strategia, esposti separatamente nella sezione avanzata.
    """
    technical = TechnicalBot()
    disciplined = DisciplinedBot()
    statistical = StatisticalBot(model_type=ml_model)
    return {b.name: b for b in (technical, disciplined, statistical)}


def periods_per_year_for_timeframe(timeframe: str) -> float:
    mapping = {"1m": 365 * 24 * 60, "5m": 365 * 24 * 12, "15m": 365 * 24 * 4, "1h": 365 * 24, "1d": 365}
    return mapping.get(timeframe, 365 * 24)
