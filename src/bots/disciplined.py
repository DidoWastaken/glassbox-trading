"""Bot 3 — "Il Disciplinato": regole semplici, cuore nel risk management.

Entrata su breakout (chiusura sopra il massimo delle ultime N barre).
Il segnale d'ingresso e' deliberatamente semplice: qui il punto non e'
"indovinare" il movimento, ma dimensionare la posizione in base al
rischio e uscire con disciplina via stop-loss / take-profit.
"""

from __future__ import annotations

from .base import Action, Bot, MarketContext, Signal


class DisciplinedBot(Bot):
    """Position sizing basato sul rischio per trade, stop-loss, take-profit, esposizione massima."""

    def __init__(
        self,
        breakout_period: int = 20,
        risk_per_trade_pct: float = 0.01,
        stop_loss_pct: float = 0.02,
        take_profit_pct: float = 0.04,
        max_exposure_pct: float = 0.3,
        name: str = "Il Disciplinato",
    ):
        if breakout_period < 1:
            raise ValueError("breakout_period deve essere >= 1")
        for label, value in (
            ("risk_per_trade_pct", risk_per_trade_pct),
            ("stop_loss_pct", stop_loss_pct),
            ("take_profit_pct", take_profit_pct),
            ("max_exposure_pct", max_exposure_pct),
        ):
            if not (0 < value <= 1):
                raise ValueError(f"{label} deve essere in (0, 1]")
        self.breakout_period = breakout_period
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_exposure_pct = max_exposure_pct
        self.name = name

    def on_data(self, context: MarketContext) -> Signal:
        history = context.history
        min_bars = self.breakout_period + 1

        if len(history) < min_bars:
            return Signal(
                Action.HOLD,
                0,
                f"HOLD: dati insufficienti ({len(history)}/{min_bars} barre necessarie per il breakout)",
            )

        if context.position_qty > 0:
            return self._manage_open_position(context)
        return self._evaluate_entry(context)

    def _manage_open_position(self, context: MarketContext) -> Signal:
        avg_price = context.position_avg_price
        last_bar = context.history.iloc[-1]
        stop_price = avg_price * (1 - self.stop_loss_pct)
        take_price = avg_price * (1 + self.take_profit_pct)

        if last_bar["low"] <= stop_price:
            return Signal(
                Action.SELL,
                context.position_qty,
                f"SELL {context.position_qty:.6f} {context.symbol}: stop-loss colpito "
                f"(minimo {last_bar['low']:.2f} <= stop {stop_price:.2f}, entry {avg_price:.2f}, "
                f"-{self.stop_loss_pct * 100:.1f}%)",
            )
        if last_bar["high"] >= take_price:
            return Signal(
                Action.SELL,
                context.position_qty,
                f"SELL {context.position_qty:.6f} {context.symbol}: take-profit raggiunto "
                f"(massimo {last_bar['high']:.2f} >= target {take_price:.2f}, entry {avg_price:.2f}, "
                f"+{self.take_profit_pct * 100:.1f}%)",
            )
        return Signal(
            Action.HOLD,
            0,
            f"HOLD: posizione aperta su {context.symbol}, in attesa di stop ({stop_price:.2f}) "
            f"o target ({take_price:.2f})",
        )

    def _evaluate_entry(self, context: MarketContext) -> Signal:
        history = context.history
        prior_highs = history["high"].iloc[-(self.breakout_period + 1) : -1]
        breakout_level = prior_highs.max()
        entry_price = context.last_price

        if entry_price <= breakout_level:
            return Signal(
                Action.HOLD,
                0,
                f"HOLD: nessun breakout (chiusura {entry_price:.2f} <= massimo "
                f"{self.breakout_period} barre {breakout_level:.2f})",
            )

        stop_distance = entry_price * self.stop_loss_pct
        risk_amount = context.cash * self.risk_per_trade_pct
        risk_based_qty = risk_amount / stop_distance
        exposure_cap_qty = (context.cash * self.max_exposure_pct) / entry_price
        affordable_qty = context.cash / entry_price

        quantity = min(risk_based_qty, exposure_cap_qty, affordable_qty)

        if quantity <= 0:
            return Signal(Action.HOLD, 0, "HOLD: breakout confermato ma cassa insufficiente per entrare")

        capped_by = "esposizione massima" if exposure_cap_qty < risk_based_qty else "rischio per trade"
        return Signal(
            Action.BUY,
            quantity,
            f"BUY {quantity:.6f} {context.symbol}: breakout sopra massimo {self.breakout_period} barre "
            f"({breakout_level:.2f}), size da {capped_by} ({self.risk_per_trade_pct * 100:.1f}% rischio, "
            f"stop -{self.stop_loss_pct * 100:.1f}%, target +{self.take_profit_pct * 100:.1f}%, "
            f"max esposizione {self.max_exposure_pct * 100:.0f}%)",
        )
