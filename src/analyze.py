"""One Claude call: read his recent tweets, name his themes/leans, map them to Kalshi tickers."""
import json
from typing import Literal
import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5-5"


class Theme(BaseModel):
    theme: str
    lean: str
    conviction: Literal["low", "medium", "high"]
    tweet_ids: list[str]


class Play(BaseModel):
    ticker: str
    side: Literal["yes", "no"]
    his_yes_prob: float
    theme: str
    why: str


class Read(BaseModel):
    themes: list[Theme]
    plays: list[Play]


SYSTEM = """You read an election analyst's tweets and work out what he believes about upcoming races.

1. Themes: group his recent tweets into the handful of recurring themes he keeps pushing (e.g. a polling-error direction, a turnout story, specific races he's bullish/bearish on). For each, state which way he leans, how strongly (judge by repetition and wording, not by any single tweet), and the tweet ids that support it. Jokes, sarcasm, and quote-tweets he's mocking are not his view.

2. Plays: for each theme, find the Kalshi markets in the provided list that his view actually bears on, and estimate the probability he would put on YES (his_yes_prob, 0-1). Only use tickers that appear verbatim in the list. Include a market only when his view clearly applies to how that market resolves; skip markets where you would be guessing. Prefer the side his view favors. It is fine to return few or no plays."""


def read_tweets(tweets, markets):
    lines = "\n".join(f"[{t['id']} {t['created_at']}] {t['text']}"
                      + (f"\n    (quoting: {t['quoted']})" if t.get("quoted") else "")
                      + (f"\n    (retweet of: {t['retweeted']})" if t.get("retweeted") else "")
                      for t in tweets)
    board = "\n".join(f"{m['ticker']} | {m['event']} | {m['market']} | {m['option']} | yes {m['yes_ask']:.2f} no {m['no_ask']:.2f}"
                      for m in markets)
    msg = anthropic.Anthropic().beta.messages.parse(
        model=MODEL, max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "high"},
        system=SYSTEM,
        messages=[{"role": "user", "content": f"<tweets>\n{lines}\n</tweets>\n\n<kalshi_markets>\nticker | event | market | option | asks\n{board}\n</kalshi_markets>"}],
        output_format=Read,
    )
    if msg.stop_reason != "end_turn" or msg.parsed_output is None:
        raise RuntimeError(f"no usable read (stop_reason={msg.stop_reason}): {json.dumps(msg.stop_details and msg.stop_details.model_dump())}")
    known = {m["ticker"] for m in markets}
    read = msg.parsed_output
    read.plays = [p for p in read.plays if p.ticker in known]
    return read
