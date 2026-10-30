# kalshi_elections

Track @TonerousHyus's election takes, map them to Kalshi markets, and paper-trade the leans. Paper only: nothing here places real orders.

`python src/run.py` does one pass:

1. `tweets.py` pulls new tweets from twitterapi.io into `data/tweets.jsonl`.
2. `kalshi.py` lists open, liquid Elections/Politics markets (public API, no key).
3. `analyze.py` has Claude read the latest 400 tweets, name his themes, and map them to tickers (only runs when there are new tweets).
4. `run.py` opens a $10 paper position when his implied probability beats the ask by 5+ points after fees, settles finished markets, and writes `reports/latest.md`.

Env vars: `TWITTERAPI_IO_KEY`, `ANTHROPIC_API_KEY`, optional `NTFY_TOPIC` (push alerts via ntfy.sh).

## Status

- Tested against live Kalshi with stubbed tweets and a stubbed model call: positions open once, settle correctly.
- Not yet tested: the real twitterapi.io fetch and the real Claude call.
- To do before scheduling: the market list is ~3,100 markets (~140k tokens per call); trim it.
