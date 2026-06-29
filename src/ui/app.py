"""GUI Layer (Streamlit) — dashboard GlassBox.

Tutti i parametri di sessione sono decisi dall'utente qui, niente valori
fissi nel codice (vedi spec §9 e la discussione di progetto: "permetterei
all'utente di decidere tutto"). Avvio: `streamlit run src/ui/app.py`.

Ogni campo ha un'icona "?" (parametro `help=`) che spiega cosa fa, per
rendere lo strumento comprensibile anche a chi non conosce il trading.
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
from src.config import SessionConfig  # noqa: E402
from src.engine.backtest import run_backtest  # noqa: E402
from src.engine.broker import PaperBroker  # noqa: E402
from src.persistence.db import init_db  # noqa: E402
from src.persistence.repository import start_session  # noqa: E402
from src.ui.helpers import build_default_bots, fetch_histories, periods_per_year_for_timeframe  # noqa: E402

st.set_page_config(page_title="GlassBox", page_icon="🔍", layout="wide")

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "glassbox.db"

# Colori coerenti per ogni bot, usati in tutti i grafici e le card.
BOT_COLORS = {
    "Il Tecnico": "#2563eb",      # blu
    "Il Disciplinato": "#059669",  # verde
    "Lo Statistico": "#d946ef",    # magenta
}
BOT_ICONS = {"Il Tecnico": "📐", "Il Disciplinato": "🛡️", "Lo Statistico": "🤖"}
BOT_TAGLINE = {
    "Il Tecnico": "Regole di analisi tecnica (medie mobili + RSI). Nessun ML.",
    "Il Disciplinato": "Entrata su breakout, cuore nel risk management (stop-loss, take-profit).",
    "Lo Statistico": "Machine learning walk-forward che prevede la direzione del prezzo.",
}

CUSTOM_CSS = """
<style>
.block-container { padding-top: 2rem; max-width: 1300px; }
.gb-hero {
    background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 55%, #0ea5e9 100%);
    border-radius: 18px; padding: 28px 32px; color: #fff; margin-bottom: 18px;
    box-shadow: 0 10px 30px rgba(37, 99, 235, 0.25);
}
.gb-hero h1 { margin: 0; font-size: 2.4rem; font-weight: 800; letter-spacing: -0.02em; }
.gb-hero p { margin: 6px 0 0; font-size: 1.05rem; opacity: 0.92; }
.gb-disclaimer {
    background: #fffbeb; border: 1px solid #fde68a; color: #92400e;
    border-radius: 10px; padding: 10px 14px; font-size: 0.86rem; margin-bottom: 8px;
}
div[data-testid="stMetric"] {
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 12px 14px;
}
div[data-testid="stMetricLabel"] { font-weight: 600; }
.gb-botcard-title { font-size: 1.15rem; font-weight: 700; margin: 4px 0 2px; }
.gb-botcard-sub { color: #64748b; font-size: 0.85rem; margin-bottom: 10px; }
</style>
"""


def render_hero() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="gb-hero">'
        "<h1>🔍 GlassBox</h1>"
        "<p>Tre filosofie di trading. Stessi dati. Denaro simulato. Zero scatole nere.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="gb-disclaimer">⚠️ Strumento <b>educativo di simulazione</b>: nessun trade reale, '
        "non è consulenza finanziaria, i risultati simulati non predicono performance reali.</div>",
        unsafe_allow_html=True,
    )


def render_bot_legend() -> None:
    with st.expander("👀 Conosci i tre bot che competono", expanded=False):
        cols = st.columns(3)
        for col, name in zip(cols, BOT_COLORS):
            with col:
                st.markdown(
                    f'<div class="gb-botcard-title">{BOT_ICONS[name]} {name}</div>'
                    f'<div class="gb-botcard-sub">{BOT_TAGLINE[name]}</div>',
                    unsafe_allow_html=True,
                )


def render_sidebar() -> tuple[SessionConfig, datetime, datetime] | None:
    st.sidebar.header("⚙️ Configurazione")
    st.sidebar.caption("Decidi tu ogni parametro. Passa il mouse sulle ? per la spiegazione.")

    initial_capital = st.sidebar.number_input(
        "💰 Capitale iniziale", min_value=100.0, value=10_000.0, step=100.0,
        help="Il denaro simulato di partenza, identico per tutti e tre i bot così il confronto è equo. "
             "Nessun soldo reale è coinvolto.",
    )
    timeframe = st.sidebar.selectbox(
        "🕒 Timeframe", ["1m", "5m", "15m", "1h", "1d"], index=4,
        help="La durata di ogni candela. '1d' = una barra al giorno: veloce e con storia sufficiente perché "
             "anche Il Tecnico (medie a 200 barre) operi. Gli intraday (1m–1h) danno molte più barre e "
             "backtest più lenti.",
    )
    assets_raw = st.sidebar.text_area(
        "📊 Asset (uno per riga)", value="BTC/USDT\nETH/USDT\nAAPL",
        help="Gli strumenti su cui far competere i bot. Crypto con la barra (es. BTC/USDT), "
             "azioni senza (es. AAPL). Uno per riga.",
    )
    assets = [a.strip() for a in assets_raw.splitlines() if a.strip()]

    fee_pct = st.sidebar.slider(
        "💸 Fee per trade (%)", 0.0, 1.0, 0.1, step=0.01,
        help="Commissione applicata a ogni operazione, in percentuale del controvalore. "
             "Tenerla > 0 rende la simulazione realistica: un backtest senza fee inganna.",
    ) / 100
    slippage_pct = st.sidebar.slider(
        "🌊 Slippage (%)", 0.0, 1.0, 0.05, step=0.01,
        help="Differenza tra prezzo atteso e prezzo eseguito. Penalizza sempre chi opera "
             "(compri un po' più caro, vendi un po' più basso), come nel mercato reale.",
    ) / 100
    ml_model = st.sidebar.selectbox(
        "🤖 Modello ML (Lo Statistico)", ["random_forest", "logistic_regression"],
        help="L'algoritmo usato dal bot 'Lo Statistico'. Random Forest è più robusto su dati non lineari; "
             "Logistic Regression è più semplice e interpretabile. Entrambi restano 'glass box'.",
    )
    days_back = st.sidebar.slider(
        "📅 Giorni di storico", 7, 365, 365,
        help="Quanto indietro nel tempo scaricare i dati per il backtest. Più giorni = più barre = "
             "backtest più lungo, ma confronto su un periodo più rappresentativo.",
    )
    end = datetime.now()
    start = end - timedelta(days=days_back)

    if timeframe in ("1m", "5m", "15m", "1h"):
        st.sidebar.caption(
            "⏱️ Gli intraday generano molte barre: con range lunghi il backtest può richiedere "
            "minuti. Per una prova rapida usa '1d'."
        )

    launch = st.sidebar.button("🚀 Avvia backtest", type="primary", use_container_width=True)
    if launch:
        config = SessionConfig(
            initial_capital=initial_capital, timeframe=timeframe, assets=assets,
            fee_pct=fee_pct, slippage_pct=slippage_pct, ml_model=ml_model,
        )
        config.validate()
        return config, start, end
    return None


def run_session(config: SessionConfig, start: datetime, end: datetime) -> dict:
    with st.spinner("📡 Scarico i dati di mercato..."):
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

    with st.spinner("⚙️ Eseguo il backtest..."):
        run_backtest(broker, bots, histories)

    return {"conn": conn, "session_id": session_id, "bots": bots, "histories": histories}


def _equity_series(conn, session_id: int, bot_name: str) -> pd.Series:
    rows = conn.execute(
        "SELECT timestamp, equity FROM equity_history WHERE session_id = ? AND bot_name = ? ORDER BY timestamp",
        (session_id, bot_name),
    ).fetchall()
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series(
        [r["equity"] for r in rows], index=pd.to_datetime([r["timestamp"] for r in rows])
    )


def render_metric_cards(conn, session_id: int, bots, config: SessionConfig, equities: dict) -> None:
    periods_per_year = periods_per_year_for_timeframe(config.timeframe)
    st.subheader("🏆 Come è andata")

    for bot_name in bots:
        equity = equities.get(bot_name)
        if equity is None or equity.empty:
            continue
        trades = pd.read_sql_query(
            "SELECT * FROM trades WHERE session_id = ? AND bot_name = ?", conn, params=(session_id, bot_name)
        )
        m = compute_metrics(equity, trades, config.initial_capital, periods_per_year)
        final_equity = config.initial_capital * (1 + m["total_return_pct"] / 100)

        with st.container(border=True):
            st.markdown(
                f'<span style="color:{BOT_COLORS[bot_name]};font-weight:700;font-size:1.1rem;">'
                f'{BOT_ICONS[bot_name]} {bot_name}</span>',
                unsafe_allow_html=True,
            )
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric(
                "Valore finale", f"€ {final_equity:,.0f}", delta=f"{m['total_return_pct']:+.2f}%",
                help="Capitale a fine periodo. La variazione % sotto è il rendimento totale rispetto "
                     "al capitale iniziale (verde = guadagno, rosso = perdita).",
            )
            c2.metric(
                "Sharpe ratio", f"{m['sharpe_ratio']:.2f}",
                help="Rendimento aggiustato per il rischio (volatilità). Più alto è meglio; "
                     "sotto zero significa che il rischio corso non è stato ripagato.",
            )
            c3.metric(
                "Max drawdown", f"{m['max_drawdown_pct']:.1f}%",
                help="La peggior caduta percentuale da un picco precedente: quanto 'doloroso' è stato "
                     "il momento peggiore del periodo. Più vicino a 0 è meglio.",
            )
            c4.metric(
                "Win rate", f"{m['win_rate_pct']:.0f}%",
                help="Percentuale di operazioni chiuse in guadagno. Attenzione: un win rate alto non "
                     "garantisce profitto se le poche perdite sono grandi.",
            )
            c5.metric(
                "Operazioni", f"{m['num_trades']}",
                help="Quante operazioni (acquisti + vendite) il bot ha eseguito nel periodo.",
            )


def render_equity_chart(equities: dict) -> None:
    st.subheader("📈 Curve di equity a confronto")
    st.caption("Il valore del portafoglio di ogni bot nel tempo, partendo dallo stesso capitale.")
    fig = go.Figure()
    for bot_name, s in equities.items():
        if s.empty:
            continue
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, mode="lines", name=bot_name,
            line=dict(color=BOT_COLORS.get(bot_name), width=2.5),
        ))
    fig.update_layout(
        template="plotly_white", yaxis_title="Valore portafoglio (€)", xaxis_title=None,
        height=420, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_price_and_signals(conn, session_id: int, bots, histories: dict) -> None:
    st.subheader("🔎 Prezzi e segnali")
    st.caption("Dove e perché ogni bot ha comprato o venduto. Passa il mouse sui triangoli per la spiegazione.")
    symbol = st.selectbox(
        "Strumento da ispezionare", list(histories.keys()),
        help="Scegli un asset per vedere il suo prezzo con sovrapposti i punti di acquisto (▲) e "
             "vendita (▼) di ciascun bot.",
    )
    history = histories[symbol]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=history.index, y=history["close"], mode="lines", name="prezzo",
        line=dict(color="#94a3b8", width=1.5),
    ))
    for bot_name in bots:
        trades = conn.execute(
            "SELECT timestamp, side, price, explanation FROM trades "
            "WHERE session_id = ? AND bot_name = ? AND symbol = ? ORDER BY timestamp",
            (session_id, bot_name, symbol),
        ).fetchall()
        color = BOT_COLORS.get(bot_name, "#000")
        for side, sym in (("buy", "triangle-up"), ("sell", "triangle-down")):
            pts = [t for t in trades if t["side"] == side]
            if not pts:
                continue
            fig.add_trace(go.Scatter(
                x=[t["timestamp"] for t in pts], y=[t["price"] for t in pts], mode="markers",
                marker=dict(symbol=sym, size=11, color=color, line=dict(width=1, color="white")),
                name=f"{bot_name} {'BUY' if side == 'buy' else 'SELL'}",
                text=[t["explanation"] for t in pts], hoverinfo="text",
            ))
    fig.update_layout(
        template="plotly_white", height=460, margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="Prezzo", legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_trades_table(conn, session_id: int) -> None:
    st.subheader("📋 Storico operazioni")
    st.caption("Ogni singola operazione è ispezionabile: il 'perché' è sempre scritto in chiaro.")
    all_trades = pd.read_sql_query(
        "SELECT bot_name AS bot, timestamp AS quando, symbol AS strumento, side AS lato, "
        "price AS prezzo, quantity AS quantità, fee, explanation AS spiegazione "
        "FROM trades WHERE session_id = ? ORDER BY timestamp",
        conn, params=(session_id,),
    )
    if all_trades.empty:
        st.info("Nessuna operazione eseguita nel periodo: con pochi dati i bot possono restare in attesa. "
                "Prova ad allungare i giorni di storico o a cambiare timeframe.")
        return
    st.dataframe(
        all_trades, use_container_width=True, hide_index=True,
        column_config={
            "prezzo": st.column_config.NumberColumn(format="%.4f"),
            "quantità": st.column_config.NumberColumn(format="%.6f"),
            "fee": st.column_config.NumberColumn(format="%.4f"),
        },
    )


def render_results(result: dict, config: SessionConfig) -> None:
    conn, session_id, bots, histories = result["conn"], result["session_id"], result["bots"], result["histories"]
    equities = {name: _equity_series(conn, session_id, name) for name in bots}

    render_metric_cards(conn, session_id, bots, config, equities)
    render_equity_chart(equities)
    render_price_and_signals(conn, session_id, bots, histories)
    render_trades_table(conn, session_id)


def main() -> None:
    render_hero()
    render_bot_legend()

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
        st.info("👈 Configura la sessione nella barra laterale e premi **Avvia backtest** per far competere i tre bot.")


if __name__ == "__main__":
    main()
