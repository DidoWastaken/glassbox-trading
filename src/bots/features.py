"""Feature engineering per il Bot 1 'Lo Statistico'.

Feature deliberatamente semplici e ispezionabili: rendimenti passati,
indicatori tecnici, volume. Nessuna feature usa dati futuri.
"""

from __future__ import annotations

import pandas as pd

from .indicators import macd, rsi, sma

FEATURE_COLUMNS = ["return_1", "sma_ratio", "rsi_14", "macd_hist", "volume_chg"]


def build_features(history: pd.DataFrame) -> pd.DataFrame:
    """Ritorna un DataFrame di feature allineato all'indice di `history`.

    Le righe di warmup (dove gli indicatori non sono ancora calcolabili)
    contengono NaN e vanno scartate da chi chiama.
    """
    close = history["close"]
    volume = history["volume"]

    sma_20 = sma(close, 20)
    _, _, macd_hist = macd(close)

    features = pd.DataFrame(
        {
            "return_1": close.pct_change(),
            "sma_ratio": close / sma_20 - 1,
            "rsi_14": rsi(close, 14),
            "macd_hist": macd_hist,
            "volume_chg": volume.pct_change(),
        },
        index=history.index,
    )
    return features
