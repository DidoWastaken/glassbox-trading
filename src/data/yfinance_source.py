"""DataSource per dati azionari via yfinance.

Nota: il "realtime" gratuito di Yahoo Finance ha spesso ~15 minuti di ritardo.
Accettabile per uso didattico, da segnalare nella UI.
"""

from __future__ import annotations

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


class YFinanceDataSource(DataSource):
    """Fonte dati azionarie basata su Yahoo Finance."""

    def get_historical(
        self, symbol: str, start: datetime, end: datetime, timeframe: str
    ) -> pd.DataFrame:
        interval = _TIMEFRAME_TO_INTERVAL.get(timeframe)
        if interval is None:
            raise DataSourceError(f"timeframe non supportato da yfinance: {timeframe}")

        ticker = yf.Ticker(symbol)
        raw = ticker.history(start=start, end=end, interval=interval)
        if raw.empty:
            raise DataSourceError(f"simbolo non trovato o nessun dato: {symbol}")

        raw = raw.rename(
            columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
        )
        df = raw[["open", "high", "low", "close", "volume"]].copy()
        df.index.name = "timestamp"
        return self._validate_ohlcv(df, symbol)

    def get_latest(self, symbol: str) -> Bar:
        ticker = yf.Ticker(symbol)
        raw = ticker.history(period="1d", interval="1m")
        if raw.empty:
            raise DataSourceError(f"nessun dato recente per {symbol}")
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
