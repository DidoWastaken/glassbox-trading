# FAQ

**GlassBox esegue trade reali?**
No. È paper trading: denaro simulato su prezzi di mercato reali. Vedi il [promemoria etico](../README.md).

**Posso usarlo per decidere investimenti reali?**
No. È uno strumento educativo. I risultati simulati non predicono performance reali — leggi [not-fooling-yourself.md](not-fooling-yourself.md).

**Perché tre bot e non uno solo "migliore"?**
Il confronto è il punto: vedere come filosofie diverse (ML, regole tecniche, risk management) si comportano sugli stessi dati insegna più di un singolo numero di rendimento.

**Posso aggiungere un mio bot?**
Sì. Implementa la classe `Bot` ([`src/bots/base.py`](../src/bots/base.py)): un solo metodo, `on_data(context) -> Signal`. Guarda [`src/bots/technical.py`](../src/bots/technical.py) come esempio minimo.

**Posso aggiungere una fonte dati diversa da ccxt/yfinance?**
Sì. Implementa l'interfaccia `DataSource` ([`src/data/source.py`](../src/data/source.py)): `get_historical` e `get_latest`.

**Perché non pandas-ta per gli indicatori?**
Ha un bug noto di import (`from numpy import NaN`) sulle versioni recenti di numpy. SMA/RSI/MACD in [`src/bots/indicators.py`](../src/bots/indicators.py) sono poche righe, scritte a mano e facili da verificare — coerente con la filosofia di trasparenza.

**Cosa succede se chiudo l'app durante il live mode e la riapro dopo ore?**
Opzione B (decisione di progetto): l'app ignora il periodo di inattività e riparte dai prezzi attuali. I portafogli (cassa, posizioni, P/L) restano intatti dall'ultima sessione live — non si resetta nulla.

**Dove sono salvati i dati?**
In un file SQLite locale, `data/glassbox.db` (escluso da git).
