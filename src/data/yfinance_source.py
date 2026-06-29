"""DataSource per dati azionari via yfinance.

Nota: il "realtime" gratuito di Yahoo Finance ha spesso ~15 minuti di ritardo.
Accettabile per uso didattico, da segnalare nella UI.

yfinance ogni tanto restituisce un DataFrame vuoto in modo transitorio
(specie sotto carico o dopo altre richieste): per questo le letture
ritentano alcune volte prima di considerare il symbol davvero introvabile.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

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

# Finestra storica massima (in giorni) che Yahoo concede per ogni intervallo intraday.
# I dati al minuto/intraday hanno limiti rigidi: oltre questi, Yahoo restituisce vuoto.
# Per i dati giornalieri non c'e' limite pratico, quindi non compaiono qui.
_MAX_LOOKBACK_DAYS = {
    "1m": 7,
    "5m": 59,
    "15m": 59,
    "60m": 729,
}

_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 1.5


def _reset_yf_session() -> None:
    """Invalida cookie e crumb cachati da yfinance nel singleton di processo.

    yfinance memorizza cookie+crumb di Yahoo in un singleton che vive quanto
    il processo (es. un server Streamlit). Quei crumb scadono col tempo, ma
    yfinance non li rinfresca automaticamente su risposta vuota: da quel
    momento ogni chiamata torna vuota finche' il processo non riparte. Qui li
    azzeriamo cosi' che il tentativo successivo ne ottenga di nuovi e validi.
    Best-effort: usa attributi interni di yfinance, quindi e' difeso da try.
    """
    try:
        import yfinance.data as yfdata

        inst = yfdata.YfData()
        inst._cookie = None
        inst._crumb = None
    except Exception:  # noqa: BLE001 - reset opportunistico, l'assenza non e' un errore
        pass


def _fetch_with_retry(fetch, symbol: str, what: str) -> pd.DataFrame:
    """Esegue `fetch()` ritentando su risposta vuota o eccezione transitoria.

    Tra un tentativo e l'altro azzera cookie/crumb di yfinance: la causa piu'
    comune di vuoti persistenti in un processo long-lived e' proprio un crumb
    scaduto. Distingue un vuoto persistente (probabile symbol inesistente) da
    uno transitorio. Solleva DataSourceError solo dopo aver esaurito i tentativi.
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
            _reset_yf_session()  # forza il rinnovo di cookie/crumb prima di ritentare
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

        # Yahoo rifiuta finestre troppo ampie per gli intervalli intraday (es. 1m: max ~7 giorni).
        # Restringiamo automaticamente l'inizio al massimo concesso, cosi' la richiesta va a buon
        # fine con i dati disponibili invece di fallire. Il backtest gestisce serie di lunghezze
        # diverse tra i symbol senza problemi.
        max_days = _MAX_LOOKBACK_DAYS.get(interval)
        if max_days is not None:
            earliest_allowed = end - timedelta(days=max_days)
            if start < earliest_allowed:
                start = earliest_allowed

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
