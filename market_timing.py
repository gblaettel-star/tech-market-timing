"""
US Tech Market Timing Dashboard
================================
A composite "market regime" gauge for US tech stocks (Nasdaq-100).

No single indicator times the market — but several well-documented macro/market
variables shift the ODDS. This app aggregates seven of them into a Buy/Hold/Sell
*tilt*, shows each one's chart (the case behind the call), lets you see how they've
developed over years, and backtests the price-based signals against buy & hold.

All data is live & free from Yahoo Finance (no API key).
Run:  streamlit run market_timing.py
"""

import datetime as dt
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import signals as S

st.set_page_config(page_title="Tech Market Timing", page_icon="📈", layout="wide")

INK, MUTED, NDX_COLOR = "#1e293b", "#64748b", "rgba(100,116,139,0.55)"
SIG_ORDER = ["trend", "earnings", "credit", "curve", "breadth", "vix", "coppergold"]
HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- #
# Cached data loaders (thin wrappers over signals.py)
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=3600, show_spinner=False)
def get_prices(period="max"):
    return S.load_prices(period)


@st.cache_data(ttl=21600, show_spinner=False)
def get_earnings(tickers_key):
    return S.load_earnings_revisions(list(tickers_key))


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #
def indicator_chart(s, ndx, lb_days):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    cut = ndx.index[-1] - pd.Timedelta(days=lb_days)
    series = s["series"]
    if series is not None:
        sv = series[series.index >= cut]
        fig.add_trace(go.Scatter(x=sv.index, y=sv.values, name="indicator",
                                 line=dict(color=INK, width=2)), secondary_y=False)
        if s.get("overlay") is not None:
            ov = s["overlay"][s["overlay"].index >= cut]
            fig.add_trace(go.Scatter(x=ov.index, y=ov.values, name=s["overlay_name"],
                                     line=dict(color=S.AMBER, width=1.5, dash="dot")),
                          secondary_y=False)
        if s.get("zero"):
            fig.add_hline(y=0, line=dict(color=S.RED, width=1, dash="dash"))
        if s.get("hline") is not None:
            fig.add_hline(y=s["hline"], line=dict(color=MUTED, width=1, dash="dash"))
    nv = ndx[ndx.index >= cut]
    fig.add_trace(go.Scatter(x=nv.index, y=nv.values, name="Nasdaq-100",
                             line=dict(color=NDX_COLOR, width=1.5)), secondary_y=True)
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=1.12, x=0),
                      plot_bgcolor="white", paper_bgcolor="white")
    fig.update_yaxes(showgrid=True, gridcolor="#f1f5f9", secondary_y=False)
    fig.update_yaxes(showgrid=False, title_text="NDX", secondary_y=True, color=MUTED)
    return fig


def gauge_chart(composite):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=composite,
        number=dict(valueformat="+.2f", font=dict(size=40)),
        gauge=dict(axis=dict(range=[-1, 1], tickvals=[-1, -0.25, 0.25, 1],
                             ticktext=["Sell", "", "", "Buy"]),
                   bar=dict(color=INK, thickness=0.25),
                   steps=[dict(range=[-1, -0.25], color="#fee2e2"),
                          dict(range=[-0.25, 0.25], color="#fef3c7"),
                          dict(range=[0.25, 1], color="#dcfce7")],
                   threshold=dict(line=dict(color="black", width=3), value=composite))))
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=10, b=0), paper_bgcolor="white")
    return fig


def history_chart(hist, lb_days):
    cut = hist.index[-1] - pd.Timedelta(days=lb_days)
    h = hist[hist.index >= cut]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_hrect(y0=0.25, y1=1, fillcolor="#16a34a", opacity=0.06, line_width=0)
    fig.add_hrect(y0=-1, y1=-0.25, fillcolor="#dc2626", opacity=0.06, line_width=0)
    fig.add_trace(go.Scatter(x=h.index, y=h["composite"], name="Composite tilt",
                             line=dict(color=INK, width=2.2),
                             fill="tozeroy", fillcolor="rgba(30,41,59,0.06)"),
                  secondary_y=False)
    fig.add_hline(y=0.25, line=dict(color=S.GREEN, width=1, dash="dot"))
    fig.add_hline(y=-0.25, line=dict(color=S.RED, width=1, dash="dot"))
    fig.add_trace(go.Scatter(x=h.index, y=h["NDX"], name="Nasdaq-100",
                             line=dict(color=NDX_COLOR, width=1.6)), secondary_y=True)
    fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=1.08, x=0),
                      plot_bgcolor="white", paper_bgcolor="white")
    fig.update_yaxes(title_text="Composite (−1…+1)", range=[-1.05, 1.05],
                     showgrid=True, gridcolor="#f1f5f9", secondary_y=False)
    fig.update_yaxes(title_text="NDX", showgrid=False, color=MUTED, secondary_y=True)
    return fig


def subscore_chart(hist, lb_days):
    cut = hist.index[-1] - pd.Timedelta(days=lb_days)
    h = hist[hist.index >= cut]
    names = {"trend": "Trend", "credit": "Credit", "curve": "Yield curve",
             "breadth": "Breadth", "vix": "Volatility", "coppergold": "Copper/Gold"}
    fig = go.Figure()
    for k, nm in names.items():
        fig.add_trace(go.Scatter(x=h.index, y=h[k], name=nm, mode="lines",
                                 line=dict(width=1.4)))
    fig.add_hline(y=0, line=dict(color=MUTED, width=1, dash="dash"))
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=1.12, x=0),
                      plot_bgcolor="white", paper_bgcolor="white")
    fig.update_yaxes(range=[-1.05, 1.05], showgrid=True, gridcolor="#f1f5f9")
    return fig


def equity_chart(eq_strat, eq_hold):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=eq_hold.index, y=eq_hold.values, name="Buy & hold NDX",
                             line=dict(color=NDX_COLOR, width=1.8)))
    fig.add_trace(go.Scatter(x=eq_strat.index, y=eq_strat.values, name="Timing model",
                             line=dict(color=S.GREEN, width=2.2)))
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=1.08, x=0),
                      plot_bgcolor="white", paper_bgcolor="white")
    fig.update_yaxes(title_text="Growth of $1", showgrid=True, gridcolor="#f1f5f9")
    return fig


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
st.sidebar.header("Settings")
lookback = st.sidebar.select_slider("Chart lookback",
                                    options=["1y", "2y", "3y", "5y", "10y", "Max"], value="3y")
LB = {"1y": 365, "2y": 730, "3y": 1095, "5y": 1825, "10y": 3650, "Max": 36500}[lookback]

st.sidebar.markdown("### Your portfolio")
default_txt = "\n".join(S.read_portfolio(os.path.join(HERE, "portfolio.txt")))
pf_text = st.sidebar.text_area(
    "Tickers drive the Earnings-Revisions signal. Paste your own (comma or newline).",
    value=default_txt, height=140)
tickers = tuple(S.parse_tickers(pf_text)) or tuple(S.DEFAULT_PORTFOLIO)
st.sidebar.caption(f"{len(tickers)} tickers · earnings signal samples these names.")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption("Prices cached 1h · earnings revisions cached 6h.")

# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #
st.title("📈 US Tech Market Timing Dashboard")
st.caption("A composite regime gauge for the Nasdaq-100 — seven indicators, one "
           "Buy / Hold / Sell tilt. Live, free data from Yahoo Finance.")

with st.spinner("Loading market data…"):
    px = get_prices()
with st.spinner("Fetching analyst earnings revisions for your portfolio…"):
    earn = get_earnings(tickers)

sig, composite = S.compute_signals(px, earn)
verdict, vcolor, vsub = S.headline_for(composite)
ndx = px["^NDX"].dropna()
hist = S.historical_scores(px)

tab_now, tab_hist, tab_back = st.tabs(["🟢 Now", "📉 History", "🧪 Backtest"])

# ============================ NOW ========================================== #
with tab_now:
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.markdown(
            f"<div style='padding:18px 24px;border-radius:14px;background:{vcolor}12;"
            f"border:2px solid {vcolor};'>"
            f"<div style='font-size:14px;color:{MUTED};letter-spacing:.05em;'>CURRENT REGIME TILT</div>"
            f"<div style='font-size:54px;font-weight:800;color:{vcolor};line-height:1.1;'>{verdict}</div>"
            f"<div style='font-size:16px;color:{INK};'>{vsub}</div>"
            f"<div style='font-size:13px;color:{MUTED};margin-top:6px;'>"
            f"Composite score {composite:+.2f} &nbsp;·&nbsp; updated {dt.datetime.now():%b %d, %Y %H:%M}</div>"
            f"</div>", unsafe_allow_html=True)
        st.markdown("")
        cols = st.columns(len(S.WEIGHTS))
        for col, k in zip(cols, sorted(S.WEIGHTS, key=lambda k: -sig[k]["score"])):
            lab, lc = S.label_for(sig[k]["score"])
            col.markdown(
                f"<div style='text-align:center'>"
                f"<div style='font-size:22px'>{'🟢' if lc==S.GREEN else '🔴' if lc==S.RED else '🟡'}</div>"
                f"<div style='font-size:11px;color:{MUTED};line-height:1.2'>"
                f"{sig[k]['name'].split('—')[0].strip()}</div>"
                f"<div style='font-size:13px;font-weight:700;color:{lc}'>{sig[k]['score']:+.2f}</div>"
                f"</div>", unsafe_allow_html=True)
    with c2:
        st.plotly_chart(gauge_chart(composite), use_container_width=True,
                        config={"displayModeBar": False})

    st.markdown("---")
    st.subheader("The case behind the call")
    for k in SIG_ORDER:
        s = sig[k]
        lab, lc = S.label_for(s["score"])
        with st.expander(f"{'🟢' if lc==S.GREEN else '🔴' if lc==S.RED else '🟡'}  "
                         f"{s['name']}  —  {lab} ({s['score']:+.2f})",
                         expanded=(k in ("trend", "earnings", "credit"))):
            left, right = st.columns([1, 1.6])
            with left:
                st.metric("Current reading", s["reading"])
                st.metric("Weight in composite", f"{S.WEIGHTS[k]*100:.0f}%")
                st.markdown(f"<span style='color:{MUTED};font-size:14px'>{s['why']}</span>",
                            unsafe_allow_html=True)
            with right:
                if s["series"] is not None:
                    st.plotly_chart(indicator_chart(s, ndx, LB),
                                    use_container_width=True, config={"displayModeBar": False})
                elif k == "earnings" and earn.get("ok"):
                    tbl = earn["table"].copy()
                    tbl["fwd EPS Δ 90d"] = (tbl["mom"] * 100).map(lambda x: f"{x:+.1f}%")
                    tbl["up/down (30d)"] = tbl.apply(
                        lambda r: f"{int(r['up'])}↑ / {int(r['down'])}↓"
                        if pd.notna(r["up"]) else "—", axis=1)
                    st.dataframe(tbl[["ticker", "fwd EPS Δ 90d", "up/down (30d)"]]
                                 .rename(columns={"ticker": "Stock"}).set_index("Stock"),
                                 use_container_width=True, height=320)

# ============================ HISTORY ====================================== #
with tab_hist:
    st.subheader("How the signal has developed over time")
    st.caption("Composite tilt (recomputed daily from price history) vs the Nasdaq-100. "
               "Green band = buy zone, red band = sell zone. Earnings signal excluded here "
               "(no Yahoo history) — this is the 6 price/macro signals, reweighted.")
    st.plotly_chart(history_chart(hist, LB), use_container_width=True,
                    config={"displayModeBar": False})
    cur = hist["composite"].iloc[-1]
    win = hist["composite"][hist.index >= hist.index[-1] - pd.Timedelta(days=LB)]
    m1, m2, m3 = st.columns(3)
    m1.metric("Composite now (price signals)", f"{cur:+.2f}")
    m2.metric("1-month change", f"{cur - hist['composite'].iloc[-22]:+.2f}")
    m3.metric("% days bullish (window)", f"{(win >= 0.25).mean()*100:.0f}%")
    st.markdown("##### Each indicator over time")
    st.plotly_chart(subscore_chart(hist, LB), use_container_width=True,
                    config={"displayModeBar": False})

# ============================ BACKTEST ===================================== #
with tab_back:
    st.subheader("Would following the tilt have helped?")
    st.caption("Strategy: hold the Nasdaq-100 only while the composite tilt is at/above the "
               "threshold (acting one day later, no look-ahead); otherwise in cash. Compared "
               "to buy & hold. Uses the 6 price-based signals over all available history.")
    threshold = st.slider("Go-to-cash threshold (composite below this → out of market)",
                          -0.5, 0.5, 0.0, 0.05)
    eq_s, eq_h, ss, sh = S.backtest(px, hist, threshold=threshold)
    st.plotly_chart(equity_chart(eq_s, eq_h), use_container_width=True,
                    config={"displayModeBar": False})
    a, b, c, d = st.columns(4)
    a.metric("Timing — total return", f"{ss['total']*100:+.0f}%", f"CAGR {ss['cagr']*100:.1f}%")
    b.metric("Buy & hold — total return", f"{sh['total']*100:+.0f}%", f"CAGR {sh['cagr']*100:.1f}%")
    c.metric("Max drawdown", f"{ss['maxdd']*100:.0f}%",
             f"vs {sh['maxdd']*100:.0f}% hold", delta_color="off")
    d.metric("Time in market", f"{ss['exposure']*100:.0f}%",
             f"Sharpe {ss['sharpe']:.2f}", delta_color="off")
    st.info("📏 The point isn't to beat buy & hold on return — over a roaring tech bull a "
            "cash-when-cautious model usually trails on total gain. The win is **smaller "
            "drawdowns**: it sidesteps the worst stretches. Judge it on max-drawdown and "
            "peace of mind, not just the finish line. Past performance ≠ future results.")

# ============================ Footer ======================================= #
st.markdown("---")
with st.expander("⚠️  How to read this — and what it is NOT"):
    st.markdown(
        "- **This is a risk *tilt*, not a trade signal.** It shifts the odds; it does not "
        "predict next week. Markets can stay irrational longer than any indicator.\n"
        "- **The value is in *agreement*** — when five or six signals lean the same way, "
        "conviction is higher than any one alone.\n"
        "- **History & backtest use the 6 price/macro signals** (earnings revisions have no "
        "Yahoo history). The live 'Now' view uses all 7.\n"
        "- **Earnings signal samples your portfolio tickers**, not the whole index, and "
        "analyst estimates can be wrong or stale.\n"
        "- **Not financial advice.** It is a structured way to organize your own thinking.\n\n"
        "_Data: Yahoo Finance. Signals: price trend, forward-EPS revisions, credit spreads, "
        "yield curve, market breadth, volatility, copper/gold ratio._")
