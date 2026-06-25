"""Interfaccia astratta per le fonti di dati di mercato."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass(frozen=True)
class Bar:
    """Una candela OHLCV."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class DataSourceError(Exception):
    """Errore nel recupero o nella validazione dei dati di mercato."""


class DataSource(ABC):
    """Interfaccia comune per qualunque fonte di dati (crypto, azioni, ...).

    Chiunque voglia aggiungere una nuova fonte (Polygon.io, Alpaca, ecc.)
    deve solo implementare questi due metodi.
    """

    @abstractmethod
    def get_historical(
        self, symbol: str, start: datetime, end: datetime, timeframe: str
    ) -> pd.DataFrame:
        """Ritorna un DataFrame OHLCV indicizzato per timestamp, ordinato crescente.

        Colonne: open, high, low, close, volume.
        """

    @abstractmethod
    def get_latest(self, symbol: str) -> Bar:
        """Ritorna l'ultima candela/prezzo disponibile per il symbol."""

    @staticmethod
    def _validate_ohlcv(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Controlli minimi di sanità sui dati: colonne presenti, niente NaN, ordine temporale."""
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise DataSourceError(f"{symbol}: colonne mancanti {missing}")
        if df.empty:
            raise DataSourceError(f"{symbol}: nessun dato restituito dalla fonte")
        if df[list(required)].isna().any().any():
            raise DataSourceError(f"{symbol}: valori NaN nei dati OHLCV")
        if not df.index.is_monotonic_increasing:
            df = df.sort_index()
        return df
