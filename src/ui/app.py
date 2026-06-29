"""GUI Layer (Streamlit) — dashboard GlassBox.

Tutti i parametri di sessione sono decisi dall'utente qui, niente valori
fissi nel codice (vedi spec §9 e la discussione di progetto: "permetterei
all'utente di decidere tutto"). Avvio: `streamlit run src/ui/app.py`.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.analytics.metrics import compute_metrics  # noqa: E402
from src.bots.base import Action  # noqa: E402
from src.config import SessionConfig  # noqa: E402
from src.engine.backtest import run_backtest  # noqa: E402
from src.engine.broker import PaperBroker  # noqa: E402
from src.persistence.db import init_db  # noqa: E402
from src.persistence.repository import start_session  # noqa: E402
from src.ui.helpers import build_default_bots, fetch_histories, periods_per_year_for_timeframe  # noqa: E402

st.set_page_config(page_title="GlassBox", layout="wide")

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "glassbox.db"

DISCLAIMER = (
    "GlassBox e' uno strumento **educativo di simulazione**. Non esegue trade reali, "
    "non e' consulenza finanziaria, e i risultati simulati non predicono performance reali."
)


def render_sidebar() -> tuple[SessionConfig, datetime, datetime] | None:
    st.sidebar.header("Configurazione sessione")

    initial_capital = st.sidebar.number_input("Capitale iniziale", min_value=100.0, value=10_000.0, step=100.0)
    # Default su '1d': poche barre, backtest in pochi secondi e abbastanza storico perche'
    # anche Il Tecnico (SMA200) operi. Gli intraday danno molte piu' barre ed e' piu' lento.
    timeframe = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "1d"], index=4)
    assets_raw = st.sidebar.text_area(
        "Asset (uno per riga; crypto con '/', es. BTC/USDT; azioni senza, es. AAPL)",
        value="BTC/USDT\nETH/USDT\nAAPL",
    )
    assets = [a.strip() for a in assets_raw.splitlines() if a.strip()]

    fee_pct = st.sidebar.slider("Fee per trade (%)", 0.0, 1.0, 0.1, step=0.01) / 100
    slippage_pct = st.sidebar.slider("Slippage (%)", 0.0, 1.0, 0.05, step=0.01) / 100
    ml_model = st.sidebar.selectbox("Modello ML (Lo Statistico)", ["random_forest", "logistic_regression"])

    days_back = st.sidebar.slider("Giorni di storico per il backtest", 7, 365, 365)
    end = datetime.now()
    start = end - timedelta(days=days_back)

    if timeframe in ("1m", "5m", "15m", "1h"):
        st.sidebar.caption(
            "⏱️ Gli intraday generano molte barre: con range lunghi il backtest puo' "
            "richiedere minuti. Per una prova rapida usa '1d'."
        )

    if st.sidebar.button("Avvia backtest", type="primary"):
        config = SessionConfig(
            initial_capital=initial_capital,
            timeframe=timeframe,
            assets=assets,
            fee_pct=fee_pct,
            slippage_pct=slippage_pct,
            ml_model=ml_model,
        )
        config.validate()
        return config, start, end
    return None


def run_session(config: SessionConfig, start: datetime, end: datetime) -> dict:
    with st.spinner("Scarico i dati di mercato..."):
        histories = fetch_histories(config.assets, start, end, config.timeframe)

    conn = init_db(DB_PATH)
    session_id = start_session(
        conn, mode="backtest", initial_capital=config.initial_capital,
        timeframe=config.timeframe, fee_pct=config.fee_pct, slippage_pct=config.slippage_pct,
    )
    broker = PaperBroker(conn, session_id, fee_pct=config.fee_pct, slippage_pct=config.slippage_pct)
    bots = build_default_bots(config.ml_model)
    for bot in bots.values():
        broker.register_bot(bot.name, config.initial_capital)

    with st.spinner("Eseguo il backtest..."):
        run_backtest(broker, bots, histories)

    return {"conn": conn, "session_id": session_id, "broker": broker, "bots": bots, "histories": histories}


def render_results(result: dict, config: SessionConfig) -> None:
    conn, session_id, bots, histories = result["conn"], result["session_id"], result["bots"], result["histories"]
    periods_per_year = periods_per_year_for_timeframe(config.timeframe)

    st.subheader("Curve di equity a confronto")
    fig = go.Figure()
    equities_by_bot = {}
    for bot_name in bots:
        rows = conn.execute(
            "SELECT timestamp, equity FROM equity_history WHERE session_id = ? AND bot_name = ? ORDER BY timestamp",
            (session_id, bot_name),
        ).fetchall()
        if not rows:
            continue
        s = pd.Series([r["equity"] for r in rows], index=pd.to_datetime([r["timestamp"] for r in rows]))
        equities_by_bot[bot_name] = s
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", name=bot_name))
    fig.update_layout(yaxis_title="Equity", xaxis_title="Tempo")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Metriche")
    metric_rows = []
    for bot_name, equity in equities_by_bot.items():
        trades = pd.read_sql_query(
            "SELECT * FROM trades WHERE session_id = ? AND bot_name = ?", conn, params=(session_id, bot_name)
        )
        metrics = compute_metrics(equity, trades, config.initial_capital, periods_per_year)
        metrics["bot"] = bot_name
        metric_rows.append(metrics)
    if metric_rows:
        st.dataframe(pd.DataFrame(metric_rows).set_index("bot"))

    with st.expander("Cosa significano queste metriche?"):
        st.markdown(
            "- **Rendimento totale**: variazione percentuale del capitale dall'inizio alla fine.\n"
            "- **Sharpe ratio**: rendimento aggiustato per il rischio (volatilita'). Piu' alto e' meglio; "
            "negativo significa che il rischio non e' stato ripagato.\n"
            "- **Max drawdown**: la peggior perdita percentuale da un picco precedente. Misura il dolore "
            "psicologico/finanziario peggiore vissuto durante il periodo.\n"
            "- **Win rate**: percentuale di operazioni chiuse in profitto."
        )

    st.subheader("Prezzi e segnali")
    symbol = st.selectbox("Symbol", list(histories.keys()))
    history = histories[symbol]
    price_fig = go.Figure()
    price_fig.add_trace(go.Scatter(x=history.index, y=history["close"], mode="lines", name="prezzo"))

    for bot_name in bots:
        trades = conn.execute(
            "SELECT timestamp, side, price, explanation FROM trades "
            "WHERE session_id = ? AND bot_name = ? AND symbol = ? ORDER BY timestamp",
            (session_id, bot_name, symbol),
        ).fetchall()
        if not trades:
            continue
        buys = [t for t in trades if t["side"] == "buy"]
        sells = [t for t in trades if t["side"] == "sell"]
        if buys:
            price_fig.add_trace(
                go.Scatter(
                    x=[t["timestamp"] for t in buys], y=[t["price"] for t in buys], mode="markers",
                    marker=dict(symbol="triangle-up", size=10, color="green"),
                    name=f"{bot_name} BUY", text=[t["explanation"] for t in buys], hoverinfo="text",
                )
            )
        if sells:
            price_fig.add_trace(
                go.Scatter(
                    x=[t["timestamp"] for t in sells], y=[t["price"] for t in sells], mode="markers",
                    marker=dict(symbol="triangle-down", size=10, color="red"),
                    name=f"{bot_name} SELL", text=[t["explanation"] for t in sells], hoverinfo="text",
                )
            )
    st.plotly_chart(price_fig, use_container_width=True)

    st.subheader("Storico operazioni (ispezionabile)")
    all_trades = pd.read_sql_query(
        "SELECT bot_name, timestamp, symbol, side, price, quantity, fee, explanation FROM trades "
        "WHERE session_id = ? ORDER BY timestamp", conn, params=(session_id,),
    )
    st.dataframe(all_trades, use_container_width=True)


def main() -> None:
    st.title("GlassBox")
    st.caption("Tre filosofie di trading, stessi dati, denaro simulato.")
    st.warning(DISCLAIMER)

    result_state = st.session_state.get("result")
    config_state = st.session_state.get("config")

    sidebar_result = render_sidebar()
    if sidebar_result is not None:
        config, start, end = sidebar_result
        st.session_state["result"] = run_session(config, start, end)
        st.session_state["config"] = config
        result_state = st.session_state["result"]
        config_state = config

    if result_state is not None:
        render_results(result_state, config_state)
    else:
        st.info("Configura la sessione nella barra laterale e premi 'Avvia backtest'.")


if __name__ == "__main__":
    main()
