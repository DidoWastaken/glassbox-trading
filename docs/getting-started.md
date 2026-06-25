# Avvio in 5 minuti

## 1. Installa le dipendenze

```bash
git clone https://github.com/DidoWastaken/glassbox-trading.git
cd glassbox-trading
python -m venv .venv
.venv\Scripts\activate   # Windows; su Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Avvia la dashboard

```bash
streamlit run src/ui/app.py
```

Si apre nel browser su `http://localhost:8501`.

## 3. Configura una sessione

Nella barra laterale scegli:
- **Capitale iniziale** (es. 10.000 simulati)
- **Timeframe** (1h, 1d, ...)
- **Asset**: uno per riga. Crypto con la barra (`BTC/USDT`), azioni senza (`AAPL`)
- **Fee e slippage** per trade
- **Modello ML** per il Bot 1 ("Lo Statistico")
- **Giorni di storico** da scaricare per il backtest

Premi **Avvia backtest**.

## 4. Leggi i risultati

- **Curve di equity**: i tre bot a confronto sullo stesso capitale e sui stessi dati.
- **Metriche**: rendimento, Sharpe, max drawdown, win rate per ciascun bot.
- **Prezzi e segnali**: scegli un asset e vedi dove ogni bot ha comprato/venduto, con la spiegazione al passaggio del mouse.
- **Storico operazioni**: ogni singolo trade, ispezionabile riga per riga.

## Eseguire i test

```bash
pytest
```

## Avviare una sessione live (da codice)

La GUI oggi copre solo il backtest. Per il live mode, usa `LiveRunner` e `start_live_session` da [`src/engine/live.py`](../src/engine/live.py) — vedi i test in [`tests/test_live.py`](../tests/test_live.py) per un esempio completo.
