"""Interfaccia comune dei bot di trading.

Ogni bot riceve gli stessi dati di mercato ed emette un Signal con una
spiegazione testuale ispezionabile — il cuore della trasparenza GlassBox.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import pandas as pd


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass(frozen=True)
class Signal:
    """Decisione di un bot per un dato symbol in un dato istante."""

    action: Action
    quantity: float
    explanation: str

    def __post_init__(self):
        if self.action != Action.HOLD and self.quantity <= 0:
            raise ValueError(f"{self.action}: quantity deve essere positiva")


@dataclass
class MarketContext:
    """Tutto ciò che un bot vede per decidere: solo passato e presente, mai il futuro.

    `history` deve già essere tagliata fino all'istante corrente incluso,
    per evitare ogni leakage temporale.
    """

    symbol: str
    history: pd.DataFrame  # colonne: open, high, low, close, volume; indice timestamp crescente
    cash: float
    position_qty: float
    position_avg_price: float | None

    @property
    def last_price(self) -> float:
        return float(self.history["close"].iloc[-1])


class Bot(ABC):
    """Classe base per tutti i bot. Ogni bot implementa solo `on_data`."""

    name: str

    @abstractmethod
    def on_data(self, context: MarketContext) -> Signal:
        """Riceve il contesto di mercato corrente e ritorna un Signal."""
