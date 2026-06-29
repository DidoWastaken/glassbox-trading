"""Bot 1 — "Lo Statistico": ML su dati storici per prevedere la direzione del prezzo.

Il piu' sperimentale e il piu' a rischio overfitting (vedi spec). Per questo:
- target = classificazione binaria (su/giu'), non un valore di prezzo.
- modello di default semplice e interpretabile (Random Forest o Logistic
  Regression), niente reti neurali.
- **validazione walk-forward obbligatoria**: il modello viene riallenato a
  ogni chiamata usando solo barre passate; la barra piu' recente (quella su
  cui si decide) non entra mai nel training, perche' la sua label dipende
  dalla barra successiva che ancora non e' accaduta. Nessun mescolamento
  passato/futuro.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from .base import Action, Bot, MarketContext, Signal
from .features import FEATURE_COLUMNS, build_features


class StatisticalBot(Bot):
    """Predice la direzione della prossima barra con un modello allenato walk-forward."""

    # Warmup necessario agli indicatori (SMA20, RSI14, MACD26) prima di dare valori validi.
    _FEATURE_WARMUP = 45

    def __init__(
        self,
        model_type: str = "random_forest",
        train_window: int = 200,
        confidence_threshold: float = 0.58,
        buy_fraction: float = 0.25,
        retrain_every: int = 10,
        trend_filter_period: int = 50,
        random_state: int = 42,
        name: str = "Lo Statistico",
    ):
        if model_type not in ("random_forest", "logistic_regression"):
            raise ValueError(f"model_type non supportato: {model_type}")
        if train_window < 20:
            raise ValueError("train_window deve essere >= 20 per avere un training set minimamente sensato")
        if not (0.5 <= confidence_threshold < 1):
            raise ValueError("confidence_threshold deve essere in [0.5, 1)")
        if not (0 < buy_fraction <= 1):
            raise ValueError("buy_fraction deve essere in (0, 1]")
        if retrain_every < 1:
            raise ValueError("retrain_every deve essere >= 1")
        if trend_filter_period < 0:
            raise ValueError("trend_filter_period deve essere >= 0 (0 = filtro disattivato)")
        self.model_type = model_type
        self.train_window = train_window
        self.trend_filter_period = trend_filter_period
        self.confidence_threshold = confidence_threshold
        self.buy_fraction = buy_fraction
        self.retrain_every = retrain_every
        self.random_state = random_state
        self.name = name
        # Cache del modello per symbol: (modello allenato, numero di barre alla scorsa fit).
        # Riallenare a ogni barra e' inutilmente costoso; un modello allenato K barre fa e'
        # comunque addestrato solo su dati passati, quindi resta walk-forward valido.
        self._models: dict[str, tuple[object, int]] = {}

    def _make_model(self):
        if self.model_type == "random_forest":
            return RandomForestClassifier(n_estimators=100, max_depth=5, random_state=self.random_state)
        return LogisticRegression(max_iter=1000)

    def on_data(self, context: MarketContext) -> Signal:
        history = context.history
        n_bars = len(history)
        min_history = self.train_window + self._FEATURE_WARMUP + 1

        if n_bars < min_history:
            return Signal(
                Action.HOLD,
                0,
                f"HOLD: dati insufficienti per il training walk-forward "
                f"({n_bars}/{min_history} barre necessarie)",
            )

        # Le feature dell'ultima barra e il training set dipendono solo dalla coda recente.
        # Calcolarle sull'intera storia a ogni barra renderebbe il backtest O(n^2): qui ci
        # limitiamo alle barre che servono davvero (train_window + warmup).
        tail = history.tail(self.train_window + self._FEATURE_WARMUP + 5)
        features = build_features(tail).replace([np.inf, -np.inf], np.nan)

        # label[t] = 1 se close[t+1] > close[t]. Richiede il prezzo futuro: usabile
        # solo per le righe passate, mai per l'ultima riga (la sua label non e' ancora nota).
        label = (tail["close"].shift(-1) > tail["close"]).astype(float)
        label.iloc[-1] = np.nan

        dataset = features.copy()
        dataset["label"] = label
        usable = dataset.dropna()

        if len(usable) < self.train_window:
            return Signal(
                Action.HOLD,
                0,
                f"HOLD: feature non ancora stabili ({len(usable)}/{self.train_window} barre valide)",
            )

        train_set = usable.iloc[-self.train_window :]
        x_train = train_set[FEATURE_COLUMNS]
        y_train = train_set["label"]

        if y_train.nunique() < 2:
            return Signal(Action.HOLD, 0, "HOLD: nelle barre di training il prezzo si e' mosso in una sola direzione, impossibile allenare un classificatore")

        last_features = features[FEATURE_COLUMNS].iloc[[-1]]
        if last_features.isna().any(axis=None):
            return Signal(Action.HOLD, 0, "HOLD: feature non disponibili sull'ultima barra (probabile warmup)")

        # Riallena solo se non c'e' un modello per questo symbol o se sono passate
        # almeno `retrain_every` barre dall'ultima fit; altrimenti riusa quello in cache.
        cached = self._models.get(context.symbol)
        if cached is None or (n_bars - cached[1]) >= self.retrain_every:
            model = self._make_model()
            model.fit(x_train, y_train)
            self._models[context.symbol] = (model, n_bars)
        else:
            model = cached[0]
        proba = model.predict_proba(last_features)[0]
        classes = list(model.classes_)
        up_idx = classes.index(1.0)
        prob_up = proba[up_idx]
        predicted_up = prob_up >= 0.5
        confidence = prob_up if predicted_up else 1 - prob_up

        model_label = "Random Forest" if self.model_type == "random_forest" else "Logistic Regression"
        basis = (
            f"{model_label} allenato walk-forward su {self.train_window} barre passate "
            f"(feature: {', '.join(FEATURE_COLUMNS)})"
        )

        # Filtro di trend: la previsione ML guida l'ingresso, ma solo se l'asset e' in
        # salita. Evita di andare long su asset in chiaro downtrend (dove il modello su
        # dati rumorosi sbaglia spesso e le fee erodono il capitale).
        in_uptrend = True
        trend_note = ""
        if self.trend_filter_period > 0 and n_bars >= self.trend_filter_period:
            trend_sma = history["close"].tail(self.trend_filter_period).mean()
            in_uptrend = context.last_price >= trend_sma
            trend_note = f", trend {'UP' if in_uptrend else 'DOWN'} (SMA{self.trend_filter_period} {trend_sma:.2f})"

        if predicted_up and confidence >= self.confidence_threshold and context.position_qty == 0:
            if not in_uptrend:
                return Signal(
                    Action.HOLD,
                    0,
                    f"HOLD: predizione UP (prob {prob_up:.2f}) ma asset in downtrend{trend_note}: "
                    f"niente ingressi contro-tendenza. {basis}",
                )
            quantity = (context.cash * self.buy_fraction) / context.last_price
            if quantity <= 0:
                return Signal(Action.HOLD, 0, "HOLD: direzione UP prevista ma cassa insufficiente")
            return Signal(
                Action.BUY,
                quantity,
                f"BUY {quantity:.6f} {context.symbol}: predizione UP, probabilita' {prob_up:.2f}{trend_note}. {basis}",
            )

        if not predicted_up and context.position_qty > 0:
            return Signal(
                Action.SELL,
                context.position_qty,
                f"SELL {context.position_qty:.6f} {context.symbol}: predizione DOWN, "
                f"probabilita' {1 - prob_up:.2f}. {basis}",
            )

        return Signal(
            Action.HOLD,
            0,
            f"HOLD: predizione {'UP' if predicted_up else 'DOWN'} con confidenza {confidence:.2f} "
            f"{'sotto soglia ' + str(self.confidence_threshold) if confidence < self.confidence_threshold else 'ma nessuna azione necessaria'}. "
            f"{basis}",
        )
