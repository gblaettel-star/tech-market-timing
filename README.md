# 📈 US Tech Market Timing Dashboard

### ▶️ **Live app: <https://tech-market-timing-bjuy2y2vqqwzkzvsqbpt3t.streamlit.app/>**
_Open on your phone and "Add to Home Screen". (Free tier sleeps after inactivity — first visit wakes it in ~30s.)_

A composite **Buy / Hold / Sell** regime gauge for US tech (Nasdaq-100). It blends
seven leading indicators into one tilt, shows the chart behind each call, plots how
the signal has developed over years, and backtests the price-based signals against
buy & hold. All data is live and free from Yahoo Finance — **no API key**.

> A risk **tilt**, not a trade signal — and not financial advice.

## The seven signals

| Signal | What it captures | Weight |
|---|---|---|
| Trend (NDX vs 200-day) | Stay with the primary trend | 20% |
| Earnings revisions | Forward EPS of *your portfolio* being raised/cut (fundamental) | 18% |
| Credit appetite (HYG/LQD) | Bond market stress before equities crack | 15% |
| Yield curve (10y − 3mo) | Recession lead indicator | 13% |
| Market breadth (RSP/SPY) | Broad vs narrow participation | 12% |
| Volatility (VIX) | Calm vs fear regime | 12% |
| Copper / Gold | Growth optimism vs fear | 10% |

History & backtest use the 6 price/macro signals (earnings revisions have no price
history); the live **Now** tab uses all 7.

## Run locally

```bash
pip install -r requirements.txt
streamlit run market_timing.py
```

## Your portfolio

Edit `portfolio.txt` (one ticker per line) — these drive the earnings-revisions
signal. You can also paste tickers into the sidebar box for a one-off look.

## Deploy (phone-friendly, shareable link)

GitHub Pages can't run this (it's live Python). Use **Streamlit Community Cloud**:

1. Push this repo to GitHub (public).
2. Go to <https://share.streamlit.io> → **New app** → pick this repo,
   branch `main`, main file `market_timing.py`.
3. You get a URL like `https://<name>.streamlit.app` — open it on your phone,
   "Add to Home Screen", and share the link with friends.

## Daily email alerts (digest + flip alerts)

A GitHub Actions cron (`.github/workflows/daily.yml`) runs every weekday after the
US close, emails a digest, and flags the day the tilt flips.

**One-time setup — create a Gmail App Password** (you, not the app):

1. Enable 2-Step Verification on your Google account.
2. Visit <https://myaccount.google.com/apppasswords> → create one named "market-timing".
3. In the GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**, add:
   - `GMAIL_USER` — your Gmail address
   - `GMAIL_APP_PASSWORD` — the 16-character app password
   - `NOTIFY_TO` — recipient(s), comma-separated (can include friends)

Test it: **Actions tab → Daily market-timing email → Run workflow**. Or locally:

```bash
DRY_RUN=1 python notify.py   # computes + writes state/preview.html, sends nothing
```
