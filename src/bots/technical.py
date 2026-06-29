"""Bot 2 — "Il Tecnico": regole deterministiche di analisi tecnica.

Nessun ML. Crossover di medie mobili filtrato da RSI, per evitare di
comprare in ipercomprato o vendere in ipervenduto. Ogni decisione produce
una spiegazione testuale — niente scatole nere.
"""

from __future__ import annotations

from .base import Action, Bot, MarketContext, Signal
from .indicators import rsi, sma


class TechnicalBot(Bot):
    """Compra su golden cross (SMA veloce sopra SMA lenta) se non in ipercomprato.

    Vende su death cross, oppure se RSI segnala ipercomprato mentre la
    posizione è aperta.
    """

    def __init__(
        self,
        fast_period: int = 50,
        slow_period: int = 200,
        rsi_period: int = 14,
        rsi_overbought: float = 70.0,
        rsi_oversold: float = 30.0,
        buy_fraction: float = 0.25,
        name: str = "Il Tecnico",
    ):
        if fast_period >= slow_period:
            raise ValueError("fast_period deve essere minore di slow_period")
        if not (0 < buy_fraction <= 1):
            raise ValueError("buy_fraction deve essere in (0, 1]")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.buy_fraction = buy_fraction
        self.name = name

    def on_data(self, context: MarketContext) -> Signal:
        close = context.history["close"]
        min_bars = self.slow_period + 1  # +1 per poter rilevare il crossover

        if len(close) < min_bars:
            return Signal(
                Action.HOLD,
                0,
                f"HOLD: dati insufficienti ({len(close)}/{min_bars} barre necessarie per SMA{self.slow_period})",
            )

        # Per rilevare il crossover servono solo le ultime due SMA e l'ultimo RSI: bastano
        # le barre piu' recenti. Limitarsi alla coda evita di ricalcolare gli indicatori
        # sull'intera storia a ogni passo (altrimenti il backtest sarebbe O(n^2)).
        close = close.tail(self.slow_period + 5)
        sma_fast = sma(close, self.fast_period)
        sma_slow = sma(close, self.slow_period)
        rsi_values = rsi(close, self.rsi_period)

        fast_now, fast_prev = sma_fast.iloc[-1], sma_fast.iloc[-2]
        slow_now, slow_prev = sma_slow.iloc[-1], sma_slow.iloc[-2]
        rsi_now = rsi_values.iloc[-1]

        golden_cross = fast_prev <= slow_prev and fast_now > slow_now
        death_cross = fast_prev >= slow_prev and fast_now < slow_now
        price = context.last_price

        if golden_cross and rsi_now < self.rsi_overbought:
            quantity = (context.cash * self.buy_fraction) / price
            if quantity <= 0:
                return Signal(Action.HOLD, 0, "HOLD: golden cross ma cassa insufficiente per comprare")
            return Signal(
                Action.BUY,
                quantity,
                f"BUY {quantity:.6f} {context.symbol}: SMA{self.fast_period} ({fast_now:.2f}) "
                f"ha superato SMA{self.slow_period} ({slow_now:.2f}) [golden cross], "
                f"RSI={rsi_now:.1f} < {self.rsi_overbought} (non ipercomprato)",
            )

        if context.position_qty > 0 and (death_cross or rsi_now > self.rsi_overbought):
            reason = (
                f"SMA{self.fast_period} ({fast_now:.2f}) e' scesa sotto SMA{self.slow_period} "
                f"({slow_now:.2f}) [death cross]"
                if death_cross
                else f"RSI={rsi_now:.1f} > {self.rsi_overbought} (ipercomprato)"
            )
            return Signal(
                Action.SELL,
                context.position_qty,
                f"SELL {context.position_qty:.6f} {context.symbol}: {reason}",
            )

        return Signal(
            Action.HOLD,
            0,
            f"HOLD: nessuna condizione di ingresso/uscita (SMA{self.fast_period}={fast_now:.2f}, "
            f"SMA{self.slow_period}={slow_now:.2f}, RSI={rsi_now:.1f})",
        )
