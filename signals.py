"""
signals.py — shared market-timing engine
=========================================
All data loading and signal computation lives here so that BOTH the Streamlit
app (market_timing.py) and the daily email job (notify.py) use identical logic.

No Streamlit dependency on purpose — the app adds caching on top of these.

Seven signals, each scored to [-1, +1], weighted into a composite:
  >= +0.25 -> BUY ,  -0.25..+0.25 -> HOLD ,  <= -0.25 -> SELL/REDUCE
"""

import os

import numpy as np
import pandas as pd
import yfinance as yf

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
PRICE_TICKERS = ["^NDX", "^VIX", "^TNX", "^IRX", "HYG", "LQD", "RSP", "SPY", "HG=F", "GC=F"]

WEIGHTS = {
    "trend": 0.20,
    "earnings": 0.18,
    "credit": 0.15,
    "curve": 0.13,
    "breadth": 0.12,
    "vix": 0.12,
    "coppergold": 0.10,
}

# The 6 price/macro signals (everything except earnings) — used for HISTORY &
# BACKTEST, where earnings-revision data has no Yahoo history. Reweighted to 1.
PRICE_SIGNALS = [k for k in WEIGHTS if k != "earnings"]
_pw_total = sum(WEIGHTS[k] for k in PRICE_SIGNALS)
PRICE_WEIGHTS = {k: WEIGHTS[k] / _pw_total for k in PRICE_SIGNALS}

DEFAULT_PORTFOLIO = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO",
                     "TSLA", "COST", "NFLX", "AMD", "ADBE", "CSCO", "QCOM", "TXN"]

GREEN, AMBER, RED = "#16a34a", "#d97706", "#dc2626"


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def clip(x, lo=-1.0, hi=1.0):
    return float(max(lo, min(hi, x)))


def label_for(score):
    if score >= 0.33:
        return "Bullish", GREEN
    if score <= -0.33:
        return "Bearish", RED
    return "Neutral", AMBER


def headline_for(score):
    if score >= 0.25:
        return "BUY", GREEN, "Risk/reward is tilted in your favor"
    if score <= -0.25:
        return "SELL / REDUCE", RED, "Conditions favor caution and lower exposure"
    return "HOLD", AMBER, "Mixed signals — no decisive edge either way"


def read_portfolio(path="portfolio.txt"):
    """Read tickers (one per line, '#' comments allowed). Falls back to default."""
    if os.path.exists(path):
        out = []
        with open(path) as f:
            for line in f:
                t = line.split("#")[0].strip().upper()
                if t:
                    out.append(t)
        if out:
            return out
    return list(DEFAULT_PORTFOLIO)


def parse_tickers(text):
    """Parse a free-text blob (commas / spaces / newlines) into a ticker list."""
    raw = text.replace(",", " ").replace("\n", " ").split()
    seen, out = set(), []
    for t in raw:
        t = t.strip().upper()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def load_prices(period="6y"):
    raw = yf.download(PRICE_TICKERS, period=period, progress=False, auto_adjust=True)["Close"]
    return raw.ffill()


def load_earnings_revisions(tickers):
    """Aggregate forward-EPS revision momentum & breadth across `tickers`."""
    rows = []
    for tk in tickers:
        try:
            t = yf.Ticker(tk)
            try:
                info = t.get_info()
            except Exception:
                info = t.info
            mcap = info.get("marketCap") or np.nan

            trend, rev = t.eps_trend, t.eps_revisions
            if trend is None or rev is None or "+1y" not in trend.index:
                continue

            cur = trend.loc["+1y", "current"]
            d90 = trend.loc["+1y", "90daysAgo"]
            mom = (cur / d90 - 1.0) if (d90 and d90 > 0) else np.nan

            up = rev.loc["+1y", "upLast30days"] if "+1y" in rev.index else np.nan
            down = rev.loc["+1y", "downLast30days"] if "+1y" in rev.index else np.nan
            rows.append({"ticker": tk, "mcap": mcap, "mom": mom, "up": up, "down": down})
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if df.empty:
        return {"ok": False}

    w = df["mcap"].fillna(df["mcap"].median())
    w = w / w.sum() if w.sum() else np.repeat(1 / len(df), len(df))
    mom = float(np.nansum(w.values * df["mom"].fillna(0).values))

    tot_up, tot_down = df["up"].sum(skipna=True), df["down"].sum(skipna=True)
    breadth = float((tot_up - tot_down) / (tot_up + tot_down)) if (tot_up + tot_down) > 0 else 0.0

    mom_score = clip(mom / 0.05)
    breadth_score = clip(breadth)
    score = clip(0.6 * mom_score + 0.4 * breadth_score)
    return {"ok": True, "score": score, "mom": mom, "breadth": breadth,
            "n": len(df), "table": df.sort_values("mcap", ascending=False)}


# --------------------------------------------------------------------------- #
# Current (snapshot) signals — all 7, for the live "Now" view & the email
# --------------------------------------------------------------------------- #
def compute_signals(px, earn):
    sig = {}

    ndx = px["^NDX"].dropna()
    ma200 = ndx.rolling(200).mean()
    gap = ndx.iloc[-1] / ma200.iloc[-1] - 1.0
    sig["trend"] = dict(
        name="Trend — Nasdaq-100 vs 200-day average", score=clip(gap / 0.10),
        reading=f"{gap*100:+.1f}% vs 200-day avg",
        why="Staying with the primary trend beats fighting it. Index above its 200-day "
            "average is the single most reliable 'risk-on' filter; below it, drawdowns are "
            "historically deeper and more frequent.",
        series=ndx, overlay=ma200, overlay_name="200-day avg")

    if earn.get("ok"):
        sig["earnings"] = dict(
            name="Earnings Revisions — forward EPS of your portfolio", score=earn["score"],
            reading=f"Fwd EPS {earn['mom']*100:+.1f}% (90d) · breadth {earn['breadth']:+.2f}",
            why="The only fundamental signal here. Analyst forward-EPS estimates being RAISED "
                "(not the level of earnings — that lags) leads price. Falling revisions warn the "
                "multiple is resting on softening numbers.",
            series=None)
    else:
        sig["earnings"] = dict(name="Earnings Revisions", score=0.0,
                               reading="data unavailable",
                               why="Revision data could not be fetched.", series=None)

    ratio = (px["HYG"] / px["LQD"]).dropna()
    rgap = ratio.iloc[-1] / ratio.rolling(200).mean().iloc[-1] - 1.0
    sig["credit"] = dict(
        name="Credit Appetite — junk vs investment-grade (HYG/LQD)", score=clip(rgap / 0.03),
        reading=f"{rgap*100:+.1f}% vs 200-day avg",
        why="Bond investors smell trouble before stock investors. When risky high-yield debt "
            "outperforms safe investment-grade debt, credit is relaxed and stocks have a "
            "tailwind. Credit cracking is a classic pre-equity warning.",
        series=ratio, overlay=ratio.rolling(200).mean(), overlay_name="200-day avg")

    curve = (px["^TNX"] - px["^IRX"]).dropna()
    cval = curve.iloc[-1]
    sig["curve"] = dict(
        name="Yield Curve — 10-year minus 3-month", score=clip(cval / 1.5),
        reading=f"{cval:+.2f}%  ({'inverted' if cval < 0 else 'normal'})",
        why="The most reliable recession lead-indicator on record. An inverted curve (short "
            "rates above long) has preceded every modern US recession. The lead is long "
            "(6–18 months), so treat it as a slow-moving caution dial, not a trigger.",
        series=curve, overlay=None, zero=True)

    breadth = (px["RSP"] / px["SPY"]).dropna()
    bgap = breadth.iloc[-1] / breadth.rolling(200).mean().iloc[-1] - 1.0
    sig["breadth"] = dict(
        name="Market Breadth — equal-weight vs cap-weight (RSP/SPY)", score=clip(bgap / 0.03),
        reading=f"{bgap*100:+.1f}% vs 200-day avg",
        why="A rally led by everything is healthy; one led by a few mega-caps is fragile. When "
            "the average stock (RSP) keeps pace with the cap-weighted index (SPY), participation "
            "is broad. Narrowing breadth often precedes tops.",
        series=breadth, overlay=breadth.rolling(200).mean(), overlay_name="200-day avg")

    vix = px["^VIX"].dropna()
    vval = vix.iloc[-1]
    sig["vix"] = dict(
        name="Volatility Regime — VIX (fear gauge)", score=clip((20 - vval) / 12),
        reading=f"{vval:.1f}",
        why="Calm markets (VIX < ~16) trend higher and reward staying invested; elevated VIX "
            "(> ~25) signals stress and bigger swings. Note: a sharp VIX *spike* is often "
            "contrarian — panic peaks near bottoms — so read extremes with nuance.",
        series=vix, overlay=None, hline=20)

    cg = (px["HG=F"] / px["GC=F"]).dropna()
    cggap = cg.iloc[-1] / cg.rolling(200).mean().iloc[-1] - 1.0
    sig["coppergold"] = dict(
        name="Copper / Gold — growth optimism vs fear", score=clip(cggap / 0.05),
        reading=f"{cggap*100:+.1f}% vs 200-day avg",
        why="Copper rises with industrial demand (growth); gold rises with fear. A rising "
            "copper/gold ratio signals the market is pricing expansion over recession — "
            "historically supportive of cyclical and tech equity.",
        series=cg, overlay=cg.rolling(200).mean(), overlay_name="200-day avg")

    composite = sum(WEIGHTS[k] * sig[k]["score"] for k in WEIGHTS)
    return sig, composite


# --------------------------------------------------------------------------- #
# Historical sub-scores (vectorized) — for History & Backtest tabs
# --------------------------------------------------------------------------- #
def historical_scores(px):
    """Daily time series of the 6 price-signal sub-scores + reweighted composite."""
    df = pd.DataFrame(index=px.index)

    ndx = px["^NDX"]
    df["trend"] = ((ndx / ndx.rolling(200).mean() - 1) / 0.10).clip(-1, 1)

    ratio = px["HYG"] / px["LQD"]
    df["credit"] = ((ratio / ratio.rolling(200).mean() - 1) / 0.03).clip(-1, 1)

    df["curve"] = ((px["^TNX"] - px["^IRX"]) / 1.5).clip(-1, 1)

    br = px["RSP"] / px["SPY"]
    df["breadth"] = ((br / br.rolling(200).mean() - 1) / 0.03).clip(-1, 1)

    df["vix"] = ((20 - px["^VIX"]) / 12).clip(-1, 1)

    cg = px["HG=F"] / px["GC=F"]
    df["coppergold"] = ((cg / cg.rolling(200).mean() - 1) / 0.05).clip(-1, 1)

    df = df.dropna()
    df["composite"] = sum(PRICE_WEIGHTS[k] * df[k] for k in PRICE_SIGNALS)
    df["NDX"] = ndx.reindex(df.index)
    return df


def backtest(px, hist, threshold=0.0, lag=1):
    """In-market when composite >= threshold (acting `lag` days later) vs buy & hold NDX."""
    ndx = px["^NDX"].reindex(hist.index).ffill()
    ret = ndx.pct_change().fillna(0.0)

    pos = (hist["composite"] >= threshold).astype(float).shift(lag).fillna(0.0)
    strat_ret = pos * ret

    eq_strat = (1 + strat_ret).cumprod()
    eq_hold = (1 + ret).cumprod()

    def stats(eq, r, label):
        yrs = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
        cagr = eq.iloc[-1] ** (1 / yrs) - 1
        dd = (eq / eq.cummax() - 1).min()
        vol = r.std() * np.sqrt(252)
        sharpe = (r.mean() * 252) / vol if vol else 0.0
        return {"label": label, "cagr": cagr, "maxdd": dd, "sharpe": sharpe,
                "total": eq.iloc[-1] - 1}

    s_strat = stats(eq_strat, strat_ret, "Timing model")
    s_hold = stats(eq_hold, ret, "Buy & hold")
    s_strat["exposure"] = float(pos.mean())
    return eq_strat, eq_hold, s_strat, s_hold
