"""Pull new tweets for one account from twitterapi.io (paid, unofficial X API) into data/tweets.jsonl."""
import json, os, urllib.parse, urllib.request

API = "https://api.twitterapi.io/twitter/user/last_tweets"
PAGES = 15   # 20 tweets/page; caps the first backfill and any catch-up after downtime


def _slim(t):
    q, rt = t.get("quoted_tweet") or {}, t.get("retweeted_tweet") or {}
    return {"id": str(t["id"]), "created_at": t.get("createdAt"), "url": t.get("url"),
            "text": t.get("text", ""), "is_reply": t.get("isReply", False),
            "quoted": q.get("text"), "retweeted": rt.get("text"), "likes": t.get("likeCount")}


def fetch_new(user, seen):
    """Newest-first pages until we hit a tweet we already have."""
    new, cur = [], ""
    for _ in range(PAGES):
        qs = urllib.parse.urlencode({"userName": user, "includeReplies": "true", **({"cursor": cur} if cur else {})})
        req = urllib.request.Request(f"{API}?{qs}", headers={"X-API-Key": os.environ["TWITTERAPI_IO_KEY"]})
        d = json.load(urllib.request.urlopen(req, timeout=60))
        body = d.get("data") or d   # docs show tweets both nested under data and top level
        page = [_slim(t) for t in body.get("tweets", [])]
        fresh = [t for t in page if t["id"] not in seen]
        new += fresh
        cur = d.get("next_cursor") or body.get("next_cursor")
        if len(fresh) < len(page) or not cur: break
    return new
