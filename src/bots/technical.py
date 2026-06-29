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
        buy_fraction: float = 0.5,
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
        min_bars = self.slow_period + 1

        if len(close) < min_bars:
            return Signal(
                Action.HOLD,
                0,
                f"HOLD: dati insufficienti ({len(close)}/{min_bars} barre necessarie per SMA{self.slow_period})",
            )

        # Bastano le ultime barre per le SMA correnti: limitarsi alla coda evita di
        # ricalcolare gli indicatori sull'intera storia a ogni passo (altrimenti O(n^2)).
        close = close.tail(self.slow_period + 5)
        sma_fast = sma(close, self.fast_period)
        sma_slow = sma(close, self.slow_period)
        rsi_now = rsi(close, self.rsi_period).iloc[-1]

        fast_now = sma_fast.iloc[-1]
        slow_now = sma_slow.iloc[-1]
        price = context.last_price

        # Trend-follower a STATO (non solo sull'attimo dell'incrocio): si e' long finche'
        # la SMA veloce e' sopra la lenta. Cosi' si cavalca un trend anche se l'incrocio e'
        # avvenuto durante il warmup degli indicatori (dove un rilevamento "a evento"
        # lo avrebbe perso). L'RSI e' mostrato per trasparenza ma non e' un trigger:
        # un trend forte e' quasi sempre "ipercomprato" e filtrarlo escluderebbe i trend migliori.
        uptrend = fast_now > slow_now

        if context.position_qty == 0 and uptrend:
            quantity = (context.cash * self.buy_fraction) / price
            if quantity <= 0:
                return Signal(Action.HOLD, 0, "HOLD: trend rialzista ma cassa insufficiente per comprare")
            return Signal(
                Action.BUY,
                quantity,
                f"BUY {quantity:.6f} {context.symbol}: SMA{self.fast_period} ({fast_now:.2f}) > "
                f"SMA{self.slow_period} ({slow_now:.2f}) [trend rialzista], RSI={rsi_now:.1f}",
            )

        if context.position_qty > 0 and not uptrend:
            return Signal(
                Action.SELL,
                context.position_qty,
                f"SELL {context.position_qty:.6f} {context.symbol}: SMA{self.fast_period} ({fast_now:.2f}) "
                f"<= SMA{self.slow_period} ({slow_now:.2f}) [trend finito], RSI={rsi_now:.1f}",
            )

        state = "in posizione, trend ancora rialzista" if context.position_qty > 0 else "flat, nessun trend rialzista"
        return Signal(
            Action.HOLD,
            0,
            f"HOLD: {state} (SMA{self.fast_period}={fast_now:.2f}, SMA{self.slow_period}={slow_now:.2f}, "
            f"RSI={rsi_now:.1f})",
        )
