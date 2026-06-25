# Bot 2 — "Il Tecnico"

Codice: [`src/bots/technical.py`](../../src/bots/technical.py)

Regole deterministiche di analisi tecnica, nessun machine learning.

## Logica

- **Entrata**: golden cross — la SMA veloce supera la SMA lenta — *e* l'RSI non è in ipercomprato.
- **Uscita**: death cross — la SMA veloce scende sotto la SMA lenta — *oppure* l'RSI segnala ipercomprato mentre la posizione è aperta.

## Parametri

| Parametro | Default | Significato |
|---|---|---|
| `fast_period` | 50 | periodo della SMA veloce |
| `slow_period` | 200 | periodo della SMA lenta |
| `rsi_period` | 14 | periodo dell'RSI |
| `rsi_overbought` | 70 | soglia di ipercomprato |
| `rsi_oversold` | 30 | soglia di ipervenduto (riservata per estensioni future) |
| `buy_fraction` | 0.25 | frazione della cassa investita a ogni BUY |

## Perché è un buon primo bot

Ogni decisione è una formula verificabile a mano: basta guardare due medie mobili e un RSI. Nessuna sorpresa, nessuna scatola nera — è il bot più facile da controllare quando si dubita di un risultato.
