"""Public (no-auth) Kalshi reads: open election/politics markets, single-market lookups.
Prices come back as *_dollars strings. Sub-titles are labels only; rules_primary is
what actually decides a market, so check it on Kalshi before trading anything for real."""
import json, time, urllib.request, urllib.error

B = "https://api.elections.kalshi.com/trade-api/v2"
CATEGORIES = {"Elections", "Politics"}
MIN_EVENT_VOLUME = 10_000      # contracts traded across the event; drops thin novelty markets
LAST_EXPIRY = "2027-02-01"     # midterm races + chamber control (seated Jan 2027)


def get(path, tries=8):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(f"{B}{path}", timeout=60))
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500: raise
        except urllib.error.URLError:
            pass
        time.sleep(2 ** i)
    raise RuntimeError(f"gave up: {path}")


def open_markets():
    """Every open, liquid election/politics market resolving before LAST_EXPIRY."""
    events, cur = [], ""
    while True:
        d = get("/events?status=open&with_nested_markets=true&limit=200" + (f"&cursor={cur}" if cur else ""))
        events += d["events"]; cur = d.get("cursor")
        if not cur: break
        time.sleep(0.3)   # the events endpoint 429s without a pause
    out = []
    for e in events:
        if e.get("category") not in CATEGORIES: continue
        ms = [m for m in e["markets"] if m["expected_expiration_time"] < LAST_EXPIRY]
        if sum(float(m["volume_fp"]) for m in ms) < MIN_EVENT_VOLUME: continue
        for m in ms:
            out.append({"ticker": m["ticker"], "event": e["title"], "market": m["title"],
                        "option": m.get("yes_sub_title", ""),
                        "yes_ask": float(m["yes_ask_dollars"]), "no_ask": float(m["no_ask_dollars"]),
                        "volume": round(float(m["volume_fp"]))})
    return out


def market(ticker):
    return get(f"/markets/{ticker}")["market"]
