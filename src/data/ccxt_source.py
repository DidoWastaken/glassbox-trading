"""DataSource per dati crypto via ccxt."""

from __future__ import annotations

from datetime import datetime, timezone

import ccxt
import pandas as pd

from .source import Bar, DataSource, DataSourceError


class CcxtDataSource(DataSource):
    """Fonte dati crypto basata su ccxt (default: Binance)."""

    def __init__(self, exchange_id: str = "binance"):
        try:
            exchange_class = getattr(ccxt, exchange_id)
        except AttributeError as exc:
            raise DataSourceError(f"exchange ccxt non valido: {exchange_id}") from exc
        self.exchange = exchange_class()

    def get_historical(
        self, symbol: str, start: datetime, end: datetime, timeframe: str
    ) -> pd.DataFrame:
        if symbol not in self._markets():
            raise DataSourceError(f"simbolo non trovato su {self.exchange.id}: {symbol}")

        since = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        all_rows: list[list[float]] = []

        while since < end_ms:
            try:
                batch = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
            except Exception as exc:  # noqa: BLE001 - rilanciato come errore di dominio
                raise DataSourceError(f"errore fetch_ohlcv per {symbol}: {exc}") from exc
            if not batch:
                break
            all_rows.extend(batch)
            last_ts = batch[-1][0]
            if last_ts <= since:
                break
            since = last_ts + 1

        if not all_rows:
            raise DataSourceError(f"nessun dato storico per {symbol} nel range richiesto")

        df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp")
        df = df[(df.index >= pd.Timestamp(start, tz="UTC")) & (df.index <= pd.Timestamp(end, tz="UTC"))]
        return self._validate_ohlcv(df, symbol)

    def get_latest(self, symbol: str) -> Bar:
        if symbol not in self._markets():
            raise DataSourceError(f"simbolo non trovato su {self.exchange.id}: {symbol}")
        try:
            ticker = self.exchange.fetch_ticker(symbol)
        except Exception as exc:  # noqa: BLE001
            raise DataSourceError(f"errore fetch_ticker per {symbol}: {exc}") from exc

        ts = ticker.get("timestamp")
        timestamp = (
            datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else datetime.now(timezone.utc)
        )
        return Bar(
            timestamp=timestamp,
            open=ticker.get("open") or ticker["last"],
            high=ticker.get("high") or ticker["last"],
            low=ticker.get("low") or ticker["last"],
            close=ticker["last"],
            volume=ticker.get("baseVolume") or 0.0,
        )

    def _markets(self) -> dict:
        if not self.exchange.markets:
            self.exchange.load_markets()
        return self.exchange.markets
