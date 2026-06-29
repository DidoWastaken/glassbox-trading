# Bot 3 — "Il Disciplinato"

Codice: [`src/bots/disciplined.py`](../../src/bots/disciplined.py)

Regola d'ingresso semplice; il cuore è il **risk management**, non il segnale.

## Logica

- **Filtro di trend**: si entra solo se il prezzo è sopra la sua SMA a `trend_filter_period` barre. Comprare breakout in un downtrend significa "prendere coltelli che cadono".
- **Entrata**: breakout — il prezzo chiude sopra il massimo delle ultime N barre — *e* il trend è rialzista.
- **Sizing**: la quantità è calcolata dal **rischio per trade** (quanto si perde se lo stop viene colpito, diviso la distanza dello stop), con un **cap di esposizione massima** che prevale se il sizing da rischio sarebbe troppo aggressivo.
- **Uscita**: **trailing stop** — lo stop "segue" il prezzo verso l'alto e scatta se il prezzo scende di `stop_loss_pct` dal massimo raggiunto. Protegge dalle perdite *e* lascia correre i vincitori, invece di tagliarli a un target fisso (l'errore classico "taglia i guadagni, tieni le perdite", corretto in fase di miglioramento).

## Parametri

| Parametro | Default | Significato |
|---|---|---|
| `breakout_period` | 20 | barre su cui calcolare il massimo di breakout |
| `risk_per_trade_pct` | 0.01 (1%) | quota di cassa rischiata per trade |
| `stop_loss_pct` | 0.08 (8%) | distanza del trailing stop dal massimo raggiunto |
| `max_exposure_pct` | 0.30 (30%) | quota massima di cassa investibile in una singola posizione |
| `trend_filter_period` | 50 | SMA del filtro di trend (0 = filtro disattivato) |

## La lezione che insegna

A parità di segnale d'ingresso, è spesso la disciplina nell'uscita — non l'abilità di prevedere il prezzo — a fare la differenza. Un trailing stop e un filtro di trend riducono drasticamente le perdite in un mercato in calo, dove un'entrata controtendenza con take-profit stretto verrebbe massacrata dai whipsaw.
