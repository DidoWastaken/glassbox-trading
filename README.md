# GlassBox

> Banco di prova open source dove tre bot con filosofie di trading diverse competono sugli stessi dati di mercato reali, usando denaro simulato (paper trading).

GlassBox copre **crypto e azioni**, ha una **dashboard interattiva** e **memoria persistente** tra sessioni. Il nome richiama la trasparenza totale: l'opposto della "black box". Ogni decisione di ogni bot è ispezionabile e comprensibile.

## Avviso

GlassBox è uno strumento **educativo di simulazione**. Non esegue trade reali, non è consulenza finanziaria, e i risultati simulati non predicono performance reali.

## I tre bot

- **Lo Statistico** — modello ML allenato sullo storico, con validazione walk-forward obbligatoria.
- **Il Tecnico** — regole deterministiche di analisi tecnica (medie mobili, RSI, MACD).
- **Il Disciplinato** — logica strutturata con focus su risk management (position sizing, stop-loss, take-profit).

Tutti i parametri (capitale iniziale, timeframe, asset, fee, slippage) sono **configurabili dall'utente** tramite l'interfaccia — nessun valore è hardcoded.

## Avvio rapido

```bash
pip install -r requirements.txt
streamlit run src/ui/app.py
```

## Documentazione

Vedi [docs/architecture.md](docs/architecture.md) per l'architettura completa a 6 layer, e [docs/getting-started.md](docs/getting-started.md) per i primi passi.

## Licenza

MIT — vedi [LICENSE](LICENSE).
