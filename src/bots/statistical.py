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

    def __init__(
        self,
        model_type: str = "random_forest",
        train_window: int = 200,
        confidence_threshold: float = 0.55,
        buy_fraction: float = 0.25,
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
        self.model_type = model_type
        self.train_window = train_window
        self.confidence_threshold = confidence_threshold
        self.buy_fraction = buy_fraction
        self.random_state = random_state
        self.name = name

    def _make_model(self):
        if self.model_type == "random_forest":
            return RandomForestClassifier(n_estimators=100, max_depth=5, random_state=self.random_state)
        return LogisticRegression(max_iter=1000)

    def on_data(self, context: MarketContext) -> Signal:
        history = context.history
        features = build_features(history)
        features = features.replace([np.inf, -np.inf], np.nan)

        # label[t] = 1 se close[t+1] > close[t]. Richiede il prezzo futuro: usabile
        # solo per le righe passate, mai per l'ultima riga (la sua label non e' ancora nota).
        label = (history["close"].shift(-1) > history["close"]).astype(float)
        label.iloc[-1] = np.nan

        dataset = features.copy()
        dataset["label"] = label
        usable = dataset.dropna()

        min_rows = self.train_window + 1
        if len(usable) < min_rows:
            return Signal(
                Action.HOLD,
                0,
                f"HOLD: dati insufficienti per il training walk-forward "
                f"({len(usable)}/{min_rows} barre valide necessarie)",
            )

        train_set = usable.iloc[-self.train_window :]
        x_train = train_set[FEATURE_COLUMNS]
        y_train = train_set["label"]

        if y_train.nunique() < 2:
            return Signal(Action.HOLD, 0, "HOLD: nelle barre di training il prezzo si e' mosso in una sola direzione, impossibile allenare un classificatore")

        last_features = features[FEATURE_COLUMNS].iloc[[-1]]
        if last_features.isna().any(axis=None):
            return Signal(Action.HOLD, 0, "HOLD: feature non disponibili sull'ultima barra (probabile warmup)")

        model = self._make_model()
        model.fit(x_train, y_train)
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

        if predicted_up and confidence >= self.confidence_threshold and context.position_qty == 0:
            quantity = (context.cash * self.buy_fraction) / context.last_price
            if quantity <= 0:
                return Signal(Action.HOLD, 0, "HOLD: direzione UP prevista ma cassa insufficiente")
            return Signal(
                Action.BUY,
                quantity,
                f"BUY {quantity:.6f} {context.symbol}: predizione UP, probabilita' {prob_up:.2f}. {basis}",
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
