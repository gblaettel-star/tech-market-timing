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

# Larger, more readable type throughout (Garry prefers bigger fonts).
st.markdown("""
<style>
  html, body, [class*="css"]            { font-size: 16.5px; }
  .stMarkdown p, .stMarkdown li         { font-size: 1.05rem; line-height: 1.55; }
  [data-testid="stCaptionContainer"],
  .stCaption, .stCaption p              { font-size: 0.98rem !important; color:#475569; }
  [data-testid="stMetricLabel"] p       { font-size: 1.02rem; }
  [data-testid="stMetricValue"]         { font-size: 1.7rem; }
  .streamlit-expanderHeader, summary p  { font-size: 1.08rem !important; font-weight: 600; }
  button[data-baseweb="tab"] p          { font-size: 1.14rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

INK, MUTED, NDX_COLOR = "#1e293b", "#64748b", "rgba(100,116,139,0.55)"
SIG_ORDER = ["trend", "earnings", "credit", "curve", "breadth", "vix", "coppergold"]
HERE = os.path.dirname(os.path.abspath(__file__))

# Plain-language "how to read this chart" notes, shown under each diagram.
NDX_NOTE = "Faint grey line = Nasdaq-100 (right axis) so you can see how the two move together."
CHART_READ = {
    "trend": "📖 **How to read:** the dark line is the Nasdaq-100 price; the amber dotted "
             "line is its 200-day average. Price **above** amber = uptrend (bullish); "
             "**below** = downtrend (caution).",
    "credit": "📖 **How to read:** the dark line is the junk-bond ÷ safe-bond ratio; amber "
              "dotted is its 200-day average. **Above** amber = investors happily buying risk "
              f"(bullish); **below** = they're turning nervous (caution). {NDX_NOTE}",
    "curve": "📖 **How to read:** the dark line is the 10-year *minus* 3-month interest rate. "
             "**Above** the red zero line = normal (healthy); **below zero = inverted**, the "
             f"classic recession warning (long lead). {NDX_NOTE}",
    "breadth": "📖 **How to read:** the dark line is the average stock ÷ the index "
               "(equal-weight vs cap-weight). **Above** its amber 200-day average = the rally "
               f"is broad and healthy; **below** = it's narrowing and fragile. {NDX_NOTE}",
    "vix": "📖 **How to read:** the dark line is the VIX 'fear gauge'. **Below** the grey 20 "
           "line = calm markets (bullish); **above 20** = stress and bigger swings (caution). "
           f"A sharp spike is often a contrarian bottom. {NDX_NOTE}",
    "coppergold": "📖 **How to read:** the dark line is the copper ÷ gold price ratio. "
                  "**Above** its amber 200-day average = markets pricing growth over fear "
                  f"(bullish for tech); **below** = fear winning (caution). {NDX_NOTE}",
    "earnings": "📖 **How to read:** this is the change in the analysts' **forecast**, not "
                "earnings growth. **fwd EPS Δ 90d** = how much they've *raised or cut* their "
                "estimate for next year's profit over the last 90 days — e.g. +39% means the "
                "forecast is 39% higher than it was 90 days ago, **not** that earnings are 39% "
                "above this year. **up/down (30d)** = how many analysts raised vs cut last month "
                "(that's the 'breadth' — how unanimous they are). Rising, broad-based estimates "
                "tend to lead rising prices.",
}


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
def indicator_chart(s, ndx, lb_days, show_ndx=True):
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
    if show_ndx:
        nv = ndx[ndx.index >= cut]
        fig.add_trace(go.Scatter(x=nv.index, y=nv.values, name="Nasdaq-100",
                                 line=dict(color=NDX_COLOR, width=1.5)), secondary_y=True)
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=1.12, x=0),
                      plot_bgcolor="white", paper_bgcolor="white")
    fig.update_yaxes(showgrid=True, gridcolor="#f1f5f9", secondary_y=False)
    fig.update_yaxes(showgrid=False, title_text="NDX", secondary_y=True, color=MUTED)
    return fig


def thermometer_chart(composite, color):
    """Vertical 'thermometer': mercury fills from −1 up to the composite tilt,
    over red / amber / green zone bands."""
    fig = go.Figure()
    fig.add_hrect(y0=0.25, y1=1, fillcolor="#dcfce7", line_width=0, layer="below")
    fig.add_hrect(y0=-0.25, y1=0.25, fillcolor="#fef3c7", line_width=0, layer="below")
    fig.add_hrect(y0=-1, y1=-0.25, fillcolor="#fee2e2", line_width=0, layer="below")
    fig.add_trace(go.Bar(x=["Tilt"], y=[composite + 1], base=-1, width=0.55,
                         marker=dict(color=color, line=dict(color="white", width=1)),
                         hoverinfo="skip"))
    fig.add_hline(y=0.25, line=dict(color=S.GREEN, width=1, dash="dot"))
    fig.add_hline(y=-0.25, line=dict(color=S.RED, width=1, dash="dot"))
    fig.add_hline(y=composite, line=dict(color=INK, width=3),
                  annotation_text=f"  {composite:+.2f}  ",
                  annotation_position="top right",
                  annotation_font=dict(size=24, color=INK))
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=24, b=10),
                      showlegend=False, bargap=0.55,
                      plot_bgcolor="white", paper_bgcolor="white")
    fig.update_xaxes(showticklabels=False, showgrid=False, zeroline=False, fixedrange=True)
    fig.update_yaxes(range=[-1.04, 1.04], fixedrange=True,
                     tickvals=[-1, -0.25, 0, 0.25, 1],
                     ticktext=["Sell −1", "−0.25", "0", "+0.25", "Buy +1"],
                     tickfont=dict(size=15), showgrid=False, zeroline=False)
    return fig


def history_chart(hist, lb_days):
    cut = hist.index[-1] - pd.Timedelta(days=lb_days)
    h = hist[hist.index >= cut]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    # Zone bands — pinned explicitly to the composite (primary) y-axis so they don't
    # bind to the NDX secondary axis and render off-screen.
    for y0, y1, col, op in [(0.25, 1.05, "#16a34a", 0.20),
                            (-0.25, 0.25, "#f59e0b", 0.12),
                            (-1.05, -0.25, "#dc2626", 0.20)]:
        fig.add_shape(type="rect", xref="paper", x0=0, x1=1, yref="y", y0=y0, y1=y1,
                      fillcolor=col, opacity=op, line_width=0, layer="below")
    for x, y, txt, col in [(0.012, 0.92, "BUY ZONE", "#15803d"),
                           (0.012, -0.92, "SELL ZONE", "#b91c1c")]:
        fig.add_annotation(xref="paper", x=x, yref="y", y=y, text=txt, showarrow=False,
                           xanchor="left", font=dict(size=13, color=col))
    fig.add_hline(y=0.25, line=dict(color=S.GREEN, width=1.5, dash="dot"))
    fig.add_hline(y=-0.25, line=dict(color=S.RED, width=1.5, dash="dot"))
    fig.add_trace(go.Scatter(x=h.index, y=h["composite"], name="Composite tilt",
                             line=dict(color=INK, width=2.4),
                             fill="tozeroy", fillcolor="rgba(30,41,59,0.06)"),
                  secondary_y=False)
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
    """Small multiples: one clean lane per signal (instead of 6 overlapping lines)."""
    cut = hist.index[-1] - pd.Timedelta(days=lb_days)
    h = hist[hist.index >= cut]
    items = [("trend", "Trend", "#2563eb"),
             ("credit", "Credit appetite", "#0891b2"),
             ("curve", "Yield curve", "#7c3aed"),
             ("breadth", "Market breadth", "#db2777"),
             ("vix", "Volatility", "#ea580c"),
             ("coppergold", "Copper / Gold", "#ca8a04")]
    fig = make_subplots(rows=len(items), cols=1, shared_xaxes=True,
                        vertical_spacing=0.045,
                        subplot_titles=[nm for _, nm, _ in items])
    for i, (k, nm, color) in enumerate(items, 1):
        y = h[k]
        fig.add_trace(go.Scatter(x=h.index, y=y.clip(lower=0), mode="lines",
                                 line=dict(width=0), fill="tozeroy",
                                 fillcolor="rgba(22,163,74,0.16)",
                                 showlegend=False, hoverinfo="skip"), row=i, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=y.clip(upper=0), mode="lines",
                                 line=dict(width=0), fill="tozeroy",
                                 fillcolor="rgba(220,38,38,0.16)",
                                 showlegend=False, hoverinfo="skip"), row=i, col=1)
        fig.add_trace(go.Scatter(x=h.index, y=y, mode="lines",
                                 line=dict(color=color, width=2.2),
                                 showlegend=False), row=i, col=1)
        fig.add_hline(y=0, line=dict(color=MUTED, width=0.8, dash="dot"), row=i, col=1)
        fig.update_yaxes(range=[-1.15, 1.15], tickvals=[-1, 0, 1],
                         tickfont=dict(size=11), showgrid=False,
                         zeroline=False, row=i, col=1)
    # left-align the per-lane titles
    for ann in fig["layout"]["annotations"]:
        ann["x"] = 0
        ann["xanchor"] = "left"
        ann["font"] = dict(size=13.5, color=INK)
    fig.update_layout(height=120 * len(items), margin=dict(l=0, r=0, t=26, b=0),
                      plot_bgcolor="white", paper_bgcolor="white")
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
# Header + top settings bar (replaces the left sidebar to win horizontal space)
# --------------------------------------------------------------------------- #
st.title("📈 US Tech Market Timing Dashboard")
st.caption("A composite regime gauge for the Nasdaq-100 — seven indicators, one "
           "Buy / Hold / Sell tilt. Live, free data from Yahoo Finance.")

with st.expander("⚙️  Settings — chart lookback & your portfolio", expanded=False):
    sc1, sc2 = st.columns([1, 2])
    with sc1:
        lookback = st.select_slider(
            "Chart lookback",
            options=["1y", "2y", "3y", "5y", "10y", "Max"], value="3y")
        if st.button("🔄 Refresh data now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.caption("Prices cached 1h · earnings 6h.")
    with sc2:
        default_txt = "\n".join(S.read_portfolio(os.path.join(HERE, "portfolio.txt")))
        pf_text = st.text_area(
            "Your portfolio — drives the Earnings-Revisions signal "
            "(paste tickers, comma- or newline-separated).",
            value=default_txt, height=150)

LB = {"1y": 365, "2y": 730, "3y": 1095, "5y": 1825, "10y": 3650, "Max": 36500}[lookback]
tickers = tuple(S.parse_tickers(pf_text)) or tuple(S.DEFAULT_PORTFOLIO)
st.caption(f"📊 Earnings signal samples your **{len(tickers)}** portfolio tickers "
           "· open ⚙️ Settings above to change the list or lookback.")

# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #
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
    c1, c2 = st.columns([1.5, 1])
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
                f"<div style='font-size:27px'>{'🟢' if lc==S.GREEN else '🔴' if lc==S.RED else '🟡'}</div>"
                f"<div style='font-size:14px;color:{MUTED};line-height:1.25'>"
                f"{sig[k]['name'].split('—')[0].strip()}</div>"
                f"<div style='font-size:18px;font-weight:700;color:{lc}'>{sig[k]['score']:+.2f}</div>"
                f"</div>", unsafe_allow_html=True)
        st.caption("🟢 **Bullish** (score ≥ +0.33)  ·  🟡 **Neutral** (−0.33 to +0.33)  ·  "
                   "🔴 **Bearish** (≤ −0.33). Each signal is scored −1 to +1; the thermometer "
                   "blends all seven into the tilt on the right.")
    with c2:
        st.plotly_chart(thermometer_chart(composite, vcolor), use_container_width=True,
                        config={"displayModeBar": False})
        st.caption("📖 **How to read:** the mercury height is today's blended score (−1 to "
                   "+1) — the weighted average of the 7 signals on the left. **Green** zone "
                   "= buy tilt, **amber** = hold, **red** = sell. The black line marks the "
                   "exact level. It's a *tilt*, not a prediction of next week.")

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
                st.markdown(f"<span style='color:{MUTED};font-size:16px'>{s['why']}</span>",
                            unsafe_allow_html=True)
            with right:
                if s["series"] is not None:
                    st.plotly_chart(indicator_chart(s, ndx, LB, show_ndx=(k != "trend")),
                                    use_container_width=True, config={"displayModeBar": False})
                    st.caption(CHART_READ[k])
                elif k == "earnings" and earn.get("ok"):
                    tbl = earn["table"].copy()
                    tbl["fwd EPS Δ 90d"] = (tbl["mom"] * 100).map(lambda x: f"{x:+.1f}%")
                    tbl["up/down (30d)"] = tbl.apply(
                        lambda r: f"{int(r['up'])}↑ / {int(r['down'])}↓"
                        if pd.notna(r["up"]) else "—", axis=1)
                    st.dataframe(tbl[["ticker", "fwd EPS Δ 90d", "up/down (30d)"]]
                                 .rename(columns={"ticker": "Stock"}).set_index("Stock"),
                                 use_container_width=True, height=320)
                    st.caption(CHART_READ["earnings"])

# ============================ HISTORY ====================================== #
with tab_hist:
    st.subheader("How the signal has developed over time")
    st.caption("Composite tilt (recomputed daily from price history) vs the Nasdaq-100. "
               "Green band = buy zone, red band = sell zone. Earnings signal excluded here "
               "(no Yahoo history) — this is the 6 price/macro signals, reweighted.")
    st.plotly_chart(history_chart(hist, LB), use_container_width=True,
                    config={"displayModeBar": False})
    st.caption("📖 **How to read:** the dark filled line is the composite tilt over time "
               "(same −1…+1 scale as the thermometer); the faint grey line is the Nasdaq-100. "
               "Look at whether the dark line sat in the **green band** (buy zone) or dropped "
               "into the **red band** (sell zone) *before* the grey line's big moves — that's "
               "the signal trying to lead the market.")
    cur = hist["composite"].iloc[-1]
    win = hist["composite"][hist.index >= hist.index[-1] - pd.Timedelta(days=LB)]
    m1, m2, m3 = st.columns(3)
    m1.metric("Composite now (price signals)", f"{cur:+.2f}")
    m2.metric("1-month change", f"{cur - hist['composite'].iloc[-22]:+.2f}")
    m3.metric("% days bullish (window)", f"{(win >= 0.25).mean()*100:.0f}%")
    st.markdown("##### Each indicator over time")
    st.plotly_chart(subscore_chart(hist, LB), use_container_width=True,
                    config={"displayModeBar": False})
    st.caption("📖 **How to read:** each mini-panel is one signal's score over time. The "
               "**green half (above the dotted zero line)** = that signal is bullish; the "
               "**red half (below)** = bearish. Scan down a single date: when most panels are "
               "in their green half together, the composite (and the thermometer) runs hot; "
               "when they sink into red together, caution is building.")

# ============================ BACKTEST ===================================== #
with tab_back:
    st.subheader("Would stepping aside to cash have actually helped?")
    st.markdown(
        "A **‘what-if’ time machine.** Imagine putting **$1 into the Nasdaq-100 back in "
        "2008.** Then ask: *what if, instead of holding it the whole way, I'd sold out to "
        "cash every time the composite tilt turned cautious — and bought back when it "
        "recovered?* The chart replays history day by day to compare the two.")
    threshold = st.slider(
        "How cautious? — sell to cash whenever the composite tilt falls below this level",
        -0.5, 0.5, 0.0, 0.05,
        help="Slide right = sell out more easily (more time in cash); "
             "left = stay invested through more dips.")
    eq_s, eq_h, ss, sh = S.backtest(px, hist, threshold=threshold)
    st.plotly_chart(equity_chart(eq_s, eq_h), use_container_width=True,
                    config={"displayModeBar": False})
    st.caption("📖 **How to read:** both lines start at $1. **Grey** = buy the Nasdaq once and "
               "never sell. **Green** = the timing model that jumps to cash whenever the tilt "
               "drops below your slider, then buys back when it rises above. Higher line = more "
               "money; a **flat green stretch = the model was sitting in cash**, on the "
               "sidelines.")
    end_s, end_h = 1 + ss["total"], 1 + sh["total"]
    a, b, c, d = st.columns(4)
    a.metric("Timing model: $1 became", f"${end_s:,.2f}",
             f"{ss['cagr']*100:.1f}% per year", delta_color="off")
    b.metric("Buy & hold: $1 became", f"${end_h:,.2f}",
             f"{sh['cagr']*100:.1f}% per year", delta_color="off")
    c.metric("Worst drop endured", f"{ss['maxdd']*100:.0f}%",
             f"buy & hold: {sh['maxdd']*100:.0f}%", delta_color="off")
    d.metric("Time invested (rest in cash)", f"{ss['exposure']*100:.0f}%",
             f"Sharpe {ss['sharpe']:.2f}", delta_color="off")

    # Honest, adaptive verdict that reads the actual numbers.
    dd_gain = (sh["maxdd"] - ss["maxdd"]) * 100  # >0 means timing had the smaller drop
    if end_s >= end_h and dd_gain >= 0:
        st.success(f"✅ At this setting timing won on **both** counts — ended richer "
                   f"(\\${end_s:,.2f} vs \\${end_h:,.2f} per \\$1) *and* with a smaller worst "
                   "drop. That's rare; usually you trade one for the other.")
    elif dd_gain >= 8 and end_s >= 0.5 * end_h:
        st.info(f"🛡️ At this setting timing **bought you a calmer ride** — worst drop "
                f"{ss['maxdd']*100:.0f}% vs {sh['maxdd']*100:.0f}% — but gave up some upside "
                f"(\\${end_s:,.2f} vs \\${end_h:,.2f} per \\$1). A fair trade for some people.")
    else:
        st.warning(f"⚠️ At this setting timing **hurt**: \\$1 ended at **\\${end_s:,.2f}** vs "
                   f"**\\${end_h:,.2f}** just holding, while the worst drop was barely better "
                   f"({ss['maxdd']*100:.0f}% vs {sh['maxdd']*100:.0f}%). Over a long tech bull, "
                   "mechanically selling on a wobble usually backfires — you miss the sharp "
                   "rebounds. **Lesson: treat this dashboard as a risk-*awareness* tool, not an "
                   "automatic in/out switch.**")
    st.caption("Try moving the slider: you'll find there's usually *no* setting that beats buy "
               "& hold on both money *and* calm — that tension is the real lesson here. "
               "Past performance ≠ future results.")

# ============================ Footer ======================================= #
st.markdown("---")
with st.expander("⚠️  How to read this — and what it is NOT"):
    st.markdown(
        "- **Reading the scores:** every signal *and* the blended composite runs from −1 to "
        "+1. 🟢 **Bullish** = score ≥ +0.33 · 🟡 **Neutral** = between −0.33 and +0.33 · "
        "🔴 **Bearish** = score ≤ −0.33. The thermometer uses the same scale (green/amber/red "
        "bands) for the combined tilt.\n"
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
