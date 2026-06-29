"""DataSource per dati azionari via yfinance.

Nota: il "realtime" gratuito di Yahoo Finance ha spesso ~15 minuti di ritardo.
Accettabile per uso didattico, da segnalare nella UI.

yfinance ogni tanto restituisce un DataFrame vuoto in modo transitorio
(specie sotto carico o dopo altre richieste): per questo le letture
ritentano alcune volte prima di considerare il symbol davvero introvabile.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from .source import Bar, DataSource, DataSourceError

_TIMEFRAME_TO_INTERVAL = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "60m",
    "1d": "1d",
}

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.5


def _fetch_with_retry(fetch, symbol: str, what: str) -> pd.DataFrame:
    """Esegue `fetch()` ritentando su risposta vuota o eccezione transitoria.

    Distingue un vuoto persistente (probabile symbol inesistente) da un
    singolo vuoto transitorio di Yahoo. Solleva DataSourceError solo dopo
    aver esaurito i tentativi.
    """
    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            raw = fetch()
            if not raw.empty:
                return raw
        except Exception as exc:  # noqa: BLE001 - rilanciata come errore di dominio sotto
            last_error = exc
        if attempt < _MAX_ATTEMPTS:
            time.sleep(_RETRY_BACKOFF_SECONDS * attempt)

    if last_error is not None:
        raise DataSourceError(
            f"errore nel recupero di {what} per {symbol} dopo {_MAX_ATTEMPTS} tentativi: {last_error}"
        ) from last_error
    raise DataSourceError(
        f"nessun dato per {symbol} dopo {_MAX_ATTEMPTS} tentativi: symbol inesistente, "
        f"oppure Yahoo Finance momentaneamente non risponde (riprova, o usa timeframe '1d')"
    )


class YFinanceDataSource(DataSource):
    """Fonte dati azionarie basata su Yahoo Finance."""

    def get_historical(
        self, symbol: str, start: datetime, end: datetime, timeframe: str
    ) -> pd.DataFrame:
        interval = _TIMEFRAME_TO_INTERVAL.get(timeframe)
        if interval is None:
            raise DataSourceError(f"timeframe non supportato da yfinance: {timeframe}")

        ticker = yf.Ticker(symbol)
        raw = _fetch_with_retry(
            lambda: ticker.history(start=start, end=end, interval=interval), symbol, "storico"
        )

        raw = raw.rename(
            columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        )
        df = raw[["open", "high", "low", "close", "volume"]].copy()
        df.index.name = "timestamp"
        return self._validate_ohlcv(df, symbol)

    def get_latest(self, symbol: str) -> Bar:
        ticker = yf.Ticker(symbol)
        raw = _fetch_with_retry(
            lambda: ticker.history(period="1d", interval="1m"), symbol, "ultimo prezzo"
        )
        last = raw.iloc[-1]
        ts = raw.index[-1]
        timestamp = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else datetime.now(timezone.utc)
        return Bar(
            timestamp=timestamp,
            open=float(last["Open"]),
            high=float(last["High"]),
            low=float(last["Low"]),
            close=float(last["Close"]),
            volume=float(last["Volume"]),
        )
