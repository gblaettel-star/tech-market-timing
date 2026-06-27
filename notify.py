"""
notify.py — daily email job (run by GitHub Actions cron)
========================================================
Computes the current composite tilt, emails a digest every run, and flags the
day the tilt FLIPS (BUY <-> HOLD <-> SELL). Stores the last verdict in
state/last_state.json so flips can be detected.

Email is sent via Gmail SMTP. Required environment variables (GitHub Secrets):
  GMAIL_USER          your gmail address (the sender)
  GMAIL_APP_PASSWORD  a Gmail *App Password* (NOT your normal password)
  NOTIFY_TO           comma-separated recipient list (defaults to GMAIL_USER)

Run a local dry run (compute + print HTML, no send):
  DRY_RUN=1 python notify.py
"""

import datetime as dt
import json
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import signals as S

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(HERE, "state", "last_state.json")


def build_report():
    tickers = S.read_portfolio(os.path.join(HERE, "portfolio.txt"))
    px = S.load_prices()
    earn = S.load_earnings_revisions(tickers)
    sig, composite = S.compute_signals(px, earn)
    verdict, color, sub = S.headline_for(composite)
    return sig, composite, verdict, color, sub


def load_last():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(verdict, composite):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump({"verdict": verdict, "composite": round(composite, 4),
                   "date": dt.date.today().isoformat()}, f, indent=2)


def html_email(sig, composite, verdict, color, sub, prev_verdict, flipped):
    today = dt.date.today().strftime("%A, %B %d, %Y")
    rows = ""
    for k in ["trend", "earnings", "credit", "curve", "breadth", "vix", "coppergold"]:
        s = sig[k]
        _, c = S.label_for(s["score"])
        dot = "🟢" if c == S.GREEN else ("🔴" if c == S.RED else "🟡")
        rows += (f"<tr><td style='padding:6px 10px'>{dot} {s['name']}</td>"
                 f"<td style='padding:6px 10px;color:{c};font-weight:700;text-align:right'>"
                 f"{s['score']:+.2f}</td>"
                 f"<td style='padding:6px 10px;color:#64748b;text-align:right'>{s['reading']}</td></tr>")

    flip_banner = ""
    if flipped:
        flip_banner = (f"<div style='background:{color};color:#fff;padding:12px 18px;"
                       f"border-radius:10px;font-size:16px;font-weight:700;margin-bottom:16px'>"
                       f"⚠️ TILT FLIPPED: {prev_verdict} → {verdict}</div>")

    return f"""<html><body style="font-family:-apple-system,Segoe UI,Arial,sans-serif;
      color:#1e293b;max-width:640px;margin:auto">
      <h2 style="margin-bottom:2px">📈 Tech Market Timing — {today}</h2>
      <div style="color:#64748b;margin-bottom:16px">Nasdaq-100 composite regime gauge</div>
      {flip_banner}
      <div style="border:2px solid {color};border-radius:14px;padding:16px 20px;margin-bottom:18px">
        <div style="font-size:13px;color:#64748b;letter-spacing:.05em">CURRENT REGIME TILT</div>
        <div style="font-size:40px;font-weight:800;color:{color}">{verdict}</div>
        <div>{sub}</div>
        <div style="color:#64748b;font-size:13px;margin-top:4px">Composite score
          <b>{composite:+.2f}</b></div>
      </div>
      <table style="border-collapse:collapse;width:100%;font-size:14px">
        <tr style="border-bottom:1px solid #e2e8f0;color:#64748b;text-align:left">
          <th style="padding:6px 10px">Signal</th>
          <th style="padding:6px 10px;text-align:right">Score</th>
          <th style="padding:6px 10px;text-align:right">Reading</th></tr>
        {rows}
      </table>
      <p style="color:#94a3b8;font-size:12px;margin-top:18px">
        A risk <i>tilt</i>, not a trade signal — and not financial advice. Data: Yahoo Finance.
      </p></body></html>"""


def send_email(subject, html):
    user = os.environ["GMAIL_USER"]
    pw = os.environ["GMAIL_APP_PASSWORD"]
    to = [x.strip() for x in os.environ.get("NOTIFY_TO", user).split(",") if x.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(to)
    msg.attach(MIMEText(html, "html"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(user, pw)
        server.sendmail(user, to, msg.as_string())
    print(f"Sent to {to}")


def main():
    sig, composite, verdict, color, sub = build_report()
    last = load_last()
    prev = last.get("verdict")
    flipped = prev is not None and prev != verdict

    html = html_email(sig, composite, verdict, color, sub, prev, flipped)
    subject = (f"{'⚠️ FLIP → ' if flipped else ''}Tech Timing: {verdict} "
               f"({composite:+.2f}) — {dt.date.today():%b %d}")

    if os.environ.get("DRY_RUN"):
        print("=== DRY RUN ===")
        print("Subject:", subject)
        print("Flipped:", flipped, "| prev:", prev, "| now:", verdict)
        out = os.path.join(HERE, "state", "preview.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w") as f:
            f.write(html)
        print("HTML written to", out)
    else:
        send_email(subject, html)

    save_state(verdict, composite)


if __name__ == "__main__":
    main()
