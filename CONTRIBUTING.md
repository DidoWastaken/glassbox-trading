# Contribuire a GlassBox

Grazie per l'interesse! GlassBox è pensato per essere estendibile con il minimo attrito.

## Setup

```bash
git clone https://github.com/DidoWastaken/glassbox-trading.git
cd glassbox-trading
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

## Aggiungere un bot

1. Crea `src/bots/<nome>.py`, estendi `Bot` ([`src/bots/base.py`](src/bots/base.py)), implementa `on_data(context) -> Signal`.
2. **Ogni Signal deve avere una spiegazione testuale** del perché — è la regola non negoziabile del progetto.
3. Esponi il bot in `src/bots/__init__.py`.
4. Aggiungi test in `tests/test_<nome>_bot.py` con dati sintetici deterministici (vedi `tests/test_technical_bot.py` per il pattern).
5. Documenta la strategia in `docs/strategies/<nome>.md`.

## Aggiungere una fonte dati

Implementa `DataSource` ([`src/data/source.py`](src/data/source.py)): `get_historical` e `get_latest`. Valida sempre i dati con `_validate_ohlcv` o un controllo equivalente.

## Aggiungere una metrica di analytics

Aggiungi una funzione in `src/analytics/metrics.py` che prende `equity`/`trades` e ritorna un valore. Aggiungila a `compute_metrics` se deve apparire di default nella dashboard.

## Regole generali

- **Trasparenza prima di tutto**: se una decisione del codice non è ispezionabile, non va bene per GlassBox.
- **Test prima del merge**: ogni nuovo comportamento ha un test che lo dimostra con dati sintetici, non con chiamate di rete reali.
- **No overengineering**: una soluzione semplice e leggibile batte un'abstrazione precoce.
- Pull request piccole e mirate sono più facili da rivedere e da accettare.

## Codice di condotta

Sii rispettoso. Questo è un progetto educativo, non competitivo.
