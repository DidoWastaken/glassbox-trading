# Bot 1 — "Lo Statistico"

Codice: [`src/bots/statistical.py`](../../src/bots/statistical.py), feature in [`src/bots/features.py`](../../src/bots/features.py)

**Il più sperimentale e il più a rischio overfitting** dei tre. Trattalo come esperimento, non come oracolo — leggi anche [non-fooling-yourself.md](../not-fooling-yourself.md).

## Target

Classificazione binaria: il prezzo nella prossima barra sarà su o giù rispetto alla chiusura corrente. Niente regressione su un prezzo esatto — è più onesto e più difficile da ingannare con l'overfitting.

## Feature

Tutte calcolate solo su dati passati: rendimento dell'ultima barra, rapporto prezzo/SMA20, RSI(14), istogramma MACD, variazione del volume.

## Modello

Random Forest o Logistic Regression (scelta in GUI) — deliberatamente semplici e interpretabili, niente reti neurali. Coerente con la filosofia "niente scatole nere".

## Validazione walk-forward (obbligatoria)

A ogni chiamata, il modello viene **riallenato da zero** usando solo le `train_window` barre immediatamente precedenti. La barra più recente — quella su cui si decide — **non entra mai nel training**, perché la sua label dipenderebbe dal prezzo della barra successiva, che ancora non è accaduta. Questo elimina ogni mescolamento passato/futuro (data leakage). Vedi `tests/test_statistical_bot.py::test_last_bar_excluded_from_training` per la verifica automatica.

## Parametri

| Parametro | Default | Significato |
|---|---|---|
| `model_type` | `random_forest` | `random_forest` o `logistic_regression` |
| `train_window` | 200 | barre passate usate per ogni riallenamento |
| `confidence_threshold` | 0.58 | probabilità minima per agire (più alta = meno trade, meno fee) |
| `buy_fraction` | 0.25 | frazione della cassa investita a ogni BUY |
| `retrain_every` | 10 | ogni quante barre riallenare il modello (perf) |
| `trend_filter_period` | 50 | SMA del filtro di trend: long solo in uptrend (0 = off) |

La previsione ML guida l'ingresso, ma un **filtro di trend** lo consente solo quando l'asset è in salita: su dati rumorosi e in downtrend il modello sbaglia spesso e le fee erodono il capitale. Una soglia di confidenza più alta riduce il churn.

## Onestà intellettuale

Un buon risultato di backtest di questo bot **non garantisce nulla** sul mercato reale: il modello può aver trovato pattern che esistevano solo nel campione storico usato. Confrontalo sempre con Il Tecnico e Il Disciplinato sugli stessi dati prima di trarre conclusioni.
