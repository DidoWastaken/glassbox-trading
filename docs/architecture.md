# Architettura

GlassBox è organizzato in 6 layer, ciascuno con una responsabilità unica. Ogni layer dipende solo da quelli sotto di lui in questo diagramma:

```
┌─────────────────────────────────────────────┐
│  6. GUI Layer (Streamlit)                    │
├─────────────────────────────────────────────┤
│  5. Analytics Layer                          │
├─────────────────────────────────────────────┤
│  2. Strategy Layer (i 3 bot)                 │
├─────────────────────────────────────────────┤
│  3. Simulation Engine (Paper Broker)         │
├─────────────────────────────────────────────┤
│  1. Data Layer                               │
├─────────────────────────────────────────────┤
│  4. Persistence Layer (SQLite)               │
└─────────────────────────────────────────────┘
```

## 1. Data Layer (`src/data/`)

Interfaccia astratta `DataSource` ([source.py](../src/data/source.py)) con due metodi: `get_historical(symbol, start, end, timeframe)` e `get_latest(symbol)`. Due implementazioni:

- `CcxtDataSource` — crypto via [ccxt](https://github.com/ccxt/ccxt) (default: Binance).
- `YFinanceDataSource` — azioni via Yahoo Finance. Il "realtime" gratuito ha ~15 min di ritardo.

Convenzione usata altrove nel codice (`src/ui/helpers.py`): un symbol con `/` (es. `BTC/USDT`) è crypto, altrimenti è un'azione (es. `AAPL`).

Aggiungere una fonte nuova significa implementare `DataSource` e basta — nessun altro layer deve cambiare.

## 2. Strategy Layer (`src/bots/`)

Classe base `Bot` ([base.py](../src/bots/base.py)) con un solo metodo da implementare: `on_data(context: MarketContext) -> Signal`. `MarketContext` porta solo passato e presente (mai il futuro), `Signal` è `BUY`/`SELL`/`HOLD` con quantità e una **spiegazione testuale obbligatoria** — il cuore della trasparenza GlassBox.

I tre bot: [Il Tecnico](strategies/tecnico.md), [Il Disciplinato](strategies/disciplinato.md), [Lo Statistico](strategies/statistico.md).

## 3. Simulation Engine (`src/engine/`)

`PaperBroker` ([broker.py](../src/engine/broker.py)) esegue ordini a un prezzo di mercato applicando **fee e slippage configurabili** — niente fill irrealistici. Gestisce cassa, posizioni a costo medio, P/L realizzato, fee totali. Lo stesso broker serve sia il backtest (`run_backtest` in [backtest.py](../src/engine/backtest.py)) sia il live mode (`LiveRunner` in [live.py](../src/engine/live.py)).

## 4. Persistence Layer (`src/persistence/`)

SQLite, file singolo ([db.py](../src/persistence/db.py)). Tabelle: `sessions`, `bots`, `positions`, `trades`, `equity_history`. Una sessione = un'esecuzione (backtest o live) con i suoi parametri (capitale, timeframe, fee, slippage). Il live mode riprende lo stato dell'ultima sessione live (`get_previous_live_state`) invece di ripartire dal capitale iniziale — vedi [Opzione B](#ripresa-live-opzione-b) sotto.

## 5. Analytics Layer (`src/analytics/`)

Metriche calcolate da `trades` ed `equity_history` ([metrics.py](../src/analytics/metrics.py)): rendimento totale, Sharpe ratio, max drawdown, win rate. `trade_pnls` ricostruisce il P/L per singola operazione di chiusura a costo medio ponderato, indipendentemente dallo stato attuale del broker.

## 6. GUI Layer (`src/ui/`)

Dashboard Streamlit ([app.py](../src/ui/app.py)). Tutti i parametri di sessione (capitale, timeframe, asset, fee, slippage, modello ML) sono **scelti dall'utente nella sidebar** — nessun valore fisso nel codice.

## Ripresa live (Opzione B)

Decisione di progetto: alla riaccensione dopo uno stop, l'app **ignora il periodo in cui era spenta** e riparte dai prezzi attuali. I portafogli (cassa, posizioni, P/L, fee) vengono riportati intatti dalla sessione live precedente — vedi `start_live_session` in [live.py](../src/engine/live.py).
