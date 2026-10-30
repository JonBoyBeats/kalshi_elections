"""Pull new tweets -> Claude reads themes/plays -> paper-trade plays with edge -> settle -> write report.
Paper only: nothing here can place a real Kalshi order."""
import csv, datetime as dt, json, math, os, pathlib, urllib.request
import kalshi, tweets

HANDLE = "TonerousHyus"
WINDOW = 400          # most recent tweets the model reads each run
MIN_EDGE = 0.05       # his implied prob minus the ask, after fees
STAKE = 10.0          # paper dollars per play
TAKER_FEE = 0.07      # Kalshi: ceil(0.07 * C * P * (1-P)) to the cent

ROOT = pathlib.Path(__file__).resolve().parent.parent
TWEETS, TRADES, REPORT = ROOT / "data/tweets.jsonl", ROOT / "data/paper_trades.csv", ROOT / "reports/latest.md"
THEMES = ROOT / "data/themes.json"
COLS = ["opened_at", "ticker", "side", "price", "contracts", "fee", "his_yes_prob", "edge", "theme", "why", "status", "result", "pnl"]


def now(): return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
def fee(c, p): return math.ceil(TAKER_FEE * c * p * (1 - p) * 100) / 100


def load_trades():
    return list(csv.DictReader(TRADES.open())) if TRADES.exists() else []


def open_trades(read, markets, trades):
    """New paper position for each play with enough edge, once per ticker+side."""
    held = {(t["ticker"], t["side"]) for t in trades}
    by_ticker = {m["ticker"]: m for m in markets}
    opened = []
    for p in read.plays:
        if (p.ticker, p.side) in held: continue
        m = by_ticker[p.ticker]
        price = m["yes_ask"] if p.side == "yes" else m["no_ask"]
        if not 0 < price < 1: continue   # no resting offer on that side
        his = p.his_yes_prob if p.side == "yes" else 1 - p.his_yes_prob
        contracts = math.floor(STAKE / price)
        f = fee(contracts, price)
        edge = his - price - f / max(contracts, 1)
        if contracts == 0 or edge < MIN_EDGE: continue
        opened.append({"opened_at": now(), "ticker": p.ticker, "side": p.side, "price": price, "contracts": contracts,
                       "fee": f, "his_yes_prob": round(p.his_yes_prob, 3), "edge": round(edge, 3), "theme": p.theme,
                       "why": p.why, "status": "open", "result": "", "pnl": ""})
    return opened


def settle(trades):
    for t in trades:
        if t["status"] != "open": continue
        m = kalshi.market(t["ticker"])
        if m.get("result") not in ("yes", "no"): continue
        payout = int(t["contracts"]) if m["result"] == t["side"] else 0
        cost = int(t["contracts"]) * float(t["price"]) + float(t["fee"])
        t.update(status="settled", result=m["result"], pnl=round(payout - cost, 2))


def report(themes, trades, markets, new_count):
    by_ticker = {m["ticker"]: m for m in markets}
    L = [f"# @{HANDLE} → Kalshi", f"Updated {now()} · {new_count} new tweets this run", "", "## His themes", "",
         "| Theme | Lean | Conviction | Tweets |", "|---|---|---|---|"]
    L += [f"| {t['theme']} | {t['lean']} | {t['conviction']} | {len(t['tweet_ids'])} |" for t in themes.get("themes", [])]
    L += ["", "## Paper positions", "", "| Opened | Ticker | Side | Entry | Now | His P(yes) | Edge | Theme | Status | P&L |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for t in sorted(trades, key=lambda t: t["opened_at"], reverse=True):
        m = by_ticker.get(t["ticker"])
        cur = (m["yes_ask"] if t["side"] == "yes" else m["no_ask"]) if m else None
        L.append(f"| {t['opened_at'][:16]} | {t['ticker']} | {t['side']} | {float(t['price']):.2f} | "
                 f"{'' if cur is None else f'{cur:.2f}'} | {t['his_yes_prob']} | {t['edge']} | {t['theme']} | {t['status']} {t['result']} | {t['pnl']} |")
    done = [t for t in trades if t["status"] == "settled"]
    staked = sum(int(t["contracts"]) * float(t["price"]) + float(t["fee"]) for t in done)
    pnl = sum(float(t["pnl"]) for t in done)
    L += ["", f"**Settled:** {len(done)} of {len(trades)} · P&L ${pnl:+.2f} on ${staked:.2f} staked"
          + (f" ({pnl / staked:+.1%})" if staked else ""), ""]
    REPORT.parent.mkdir(exist_ok=True); REPORT.write_text("\n".join(L))


def notify(opened):
    topic = os.environ.get("NTFY_TOPIC")
    if not (topic and opened): return
    body = "\n".join(f"{t['side'].upper()} {t['ticker']} @ {t['price']:.2f} (edge {t['edge']:+.2f}) — {t['theme']}" for t in opened)
    urllib.request.urlopen(urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(),
                                                  headers={"Title": f"{len(opened)} new paper plays from @{HANDLE}"}), timeout=30)


def main():
    TWEETS.parent.mkdir(exist_ok=True)
    have = [json.loads(l) for l in TWEETS.open()] if TWEETS.exists() else []
    new = tweets.fetch_new(HANDLE, {t["id"] for t in have})
    if new:
        have = sorted(have + new, key=lambda t: int(t["id"]))
        TWEETS.write_text("".join(json.dumps(t) + "\n" for t in have))
    print(f"{len(new)} new tweets ({len(have)} total)")

    markets = kalshi.open_markets()
    print(f"{len(markets)} open election/politics markets")
    trades = load_trades()
    themes = json.loads(THEMES.read_text()) if THEMES.exists() else {}
    opened = []
    if new:   # only spend a model call when he has said something new
        import analyze
        read = analyze.read_tweets(have[-WINDOW:], markets)
        themes = read.model_dump()
        THEMES.write_text(json.dumps(themes, indent=1))
        opened = open_trades(read, markets, trades)
        trades += opened
        print(f"{len(read.themes)} themes, {len(read.plays)} plays, {len(opened)} new paper positions")

    settle(trades)
    with TRADES.open("w", newline="") as f:
        w = csv.DictWriter(f, COLS); w.writeheader(); w.writerows(trades)
    report(themes, trades, markets, len(new))
    notify(opened)


if __name__ == "__main__":
    main()
