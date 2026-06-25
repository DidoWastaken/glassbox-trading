# Bot 3 — "Il Disciplinato"

Codice: [`src/bots/disciplined.py`](../../src/bots/disciplined.py)

Regola d'ingresso semplice; il cuore è il **risk management**, non il segnale.

## Logica

- **Entrata**: breakout — il prezzo chiude sopra il massimo delle ultime N barre.
- **Sizing**: la quantità non è fissa, ma calcolata dal **rischio per trade**: quanto si è disposti a perdere se lo stop-loss viene colpito, diviso la distanza dello stop. Un **cap di esposizione massima** impedisce comunque che una singola posizione diventi troppo grande, anche se il rischio per trade lo permetterebbe.
- **Uscita**: solo stop-loss o take-profit. Mai discrezionale.

## Parametri

| Parametro | Default | Significato |
|---|---|---|
| `breakout_period` | 20 | barre su cui calcolare il massimo di breakout |
| `risk_per_trade_pct` | 0.01 (1%) | quota di cassa rischiata per trade |
| `stop_loss_pct` | 0.02 (2%) | distanza dello stop-loss dall'entrata |
| `take_profit_pct` | 0.04 (4%) | distanza del take-profit dall'entrata |
| `max_exposure_pct` | 0.30 (30%) | quota massima di cassa investibile in una singola posizione |

## La lezione che insegna

A parità di segnale d'ingresso, è spesso la disciplina nell'uscita — non l'abilità di prevedere il prezzo — a fare la differenza tra un sistema che sopravvive e uno che no.
