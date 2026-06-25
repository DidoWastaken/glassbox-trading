"""Configurazione di sessione GlassBox.

Tutti i parametri qui sono pensati per essere impostati dall'utente
tramite la GUI (Streamlit), non per essere valori fissi del codice.
I default sono solo un punto di partenza ragionevole per il primo avvio.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionConfig:
    """Parametri di una sessione di backtest/paper trading, configurabili dall'utente."""

    initial_capital: float = 10_000.0
    timeframe: str = "1h"
    assets: list[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT", "AAPL", "MSFT", "TSLA"])
    fee_pct: float = 0.001  # 0.1% per trade
    slippage_pct: float = 0.0005  # 0.05% su market order
    ml_model: str = "random_forest"  # alternativa: "logistic_regression"

    def validate(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital deve essere positivo")
        if not self.assets:
            raise ValueError("serve almeno un asset")
        if not (0 <= self.fee_pct < 1):
            raise ValueError("fee_pct deve essere in [0, 1)")
        if not (0 <= self.slippage_pct < 1):
            raise ValueError("slippage_pct deve essere in [0, 1)")
        if self.ml_model not in ("random_forest", "logistic_regression"):
            raise ValueError(f"ml_model non supportato: {self.ml_model}")
