# Bot 2 — "Il Tecnico"

Codice: [`src/bots/technical.py`](../../src/bots/technical.py)

Regole deterministiche di analisi tecnica, nessun machine learning.

## Logica

Trend-follower **a stato** (non a evento): si è long finché la SMA veloce è *sopra* la lenta.

- **Entrata**: SMA veloce > SMA lenta (trend rialzista) e nessuna posizione aperta.
- **Uscita**: SMA veloce ≤ SMA lenta (trend finito).

Si entra sullo *stato* di trend, non solo sull'attimo esatto dell'incrocio: così si cavalca un trend anche se l'incrocio è avvenuto durante il warmup degli indicatori (dove un rilevamento "a evento" lo perderebbe — un bug reale corretto dopo aver osservato che il bot non operava mai).

L'**RSI è mostrato nella spiegazione per trasparenza ma non è un trigger**: un trend forte è quasi sempre "ipercomprato", e filtrare l'entrata con l'RSI escluderebbe proprio i trend migliori (altro errore corretto in fase di miglioramento).

## Parametri

| Parametro | Default | Significato |
|---|---|---|
| `fast_period` | 50 | periodo della SMA veloce |
| `slow_period` | 200 | periodo della SMA lenta |
| `rsi_period` | 14 | periodo dell'RSI (informativo) |
| `rsi_overbought` | 70 | soglia di ipercomprato (mostrata, non operativa) |
| `buy_fraction` | 0.5 | frazione della cassa investita all'ingresso |

## Perché è un buon primo bot

Ogni decisione è una formula verificabile a mano: basta confrontare due medie mobili. In un mercato in calo resta semplicemente fuori (SMA veloce sotto la lenta), il che lo protegge dai crolli; in un trend rialzista lo cavalca finché dura.
