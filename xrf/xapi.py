"""Read-only X API v2 client. Official endpoints only; never writes to X.

Every page is one metered, cached call (rawstore.call), so interrupted runs resume where they
stopped and repeated runs cost nothing. Endpoint names, limits and prices were checked against the
official docs on 2026-11-20: docs/api_docs_findings.md and docs/DECISIONS.md (D-002).

Cost accounting: posts $0.005 and users $0.010 per object returned; counts per request. Whether
objects returned via expansions are billed is not documented, so by default they are counted
(worst case): recorded spend is an upper bound on X's bill.
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Iterator

from . import config, costs, rawstore

BASE = "https://api.x.com/2"


class XError(RuntimeError):
    pass


def _p() -> dict:
    return costs.pricing("x")


def _style() -> str:
    return config.load("pricing")["x"].get("field_style", "tweet")


def fields(kind: str = "full") -> dict:
    """Request parameters for post payloads. kind: full (collection), sweep (discovery, no user expansion),
    id (deletion checks)."""
    t = _style() == "tweet"
    fkey = "tweet.fields" if t else "post.fields"
    note = "note_tweet" if t else "note_post"
    refs = "referenced_tweets" if t else "referenced_posts"
    base = f"id,text,author_id,created_at,conversation_id,in_reply_to_user_id,lang,public_metrics,{refs},attachments,entities,{note}"
    if kind == "id":
        return {fkey: "id,created_at,author_id"}
    out = {fkey: base, "media.fields": "media_key,type,url,preview_image_url,alt_text"}
    if kind == "full":
        out["expansions"] = f"author_id,{refs}.id,{refs}.id.author_id,attachments.media_keys"
        out["user.fields"] = "id,username,name,description,public_metrics,verified,created_at"
    else:   # sweep: quoted posts (for quoted authors' ids) but no user objects
        out["expansions"] = f"{refs}.id,attachments.media_keys"
    return out


def _token() -> str:
    t = config.env_key("X_BEARER_TOKEN")
    if not t:
        raise XError("X_BEARER_TOKEN is not set")
    return t


def _count_objects(body: bytes) -> tuple[int, int, int, int]:
    d = json.loads(body)
    data = d.get("data")
    if isinstance(data, dict):
        data = [data]
    data = data or []
    inc = d.get("includes", {}) or {}
    users_main = sum(1 for x in data if isinstance(x, dict) and "username" in x)
    posts_main = len(data) - users_main
    return posts_main, users_main, len(inc.get("tweets", inc.get("posts", [])) or []), len(inc.get("users", []) or [])


def cost_of(kind: str):
    def f(status: int, body: bytes) -> tuple[float, float, str]:
        p = _p()
        if kind == "counts_all":
            return p["counts_all_request_usd"], 1, "request"
        if kind == "counts_recent":
            return p["counts_recent_request_usd"], 1, "request"
        pm, um, pi, ui = _count_objects(body)
        posts = pm + (pi if p.get("bill_expanded_posts") else 0)
        users = um + (ui if p.get("bill_expanded_users") else 0)
        return posts * p["post_read_usd"] + users * p["user_read_usd"], posts + users, "objects"
    return f


def worst_case(kind: str, n: int, params: dict) -> float:
    p = _p()
    if kind == "counts_all":
        return p["counts_all_request_usd"]
    if kind == "counts_recent":
        return p["counts_recent_request_usd"]
    if kind == "users":
        return n * p["user_read_usd"]
    exp = params.get("expansions", "")
    per_post = p["post_read_usd"] * (2 if (p.get("bill_expanded_posts") and ".id" in exp) else 1)
    users = (2 * n * p["user_read_usd"]) if (p.get("bill_expanded_users") and "author_id" in exp) else 0
    return n * per_post + users


def get(conn: sqlite3.Connection, path: str, params: dict, *, budget: str, kind: str, n: int) -> rawstore.Raw:
    def do_request():
        return _send(path, params)

    raw = rawstore.call(conn, provider="x", endpoint=path, params=params, budget=budget,
                        worst_case_usd=worst_case(kind, n, params), do_request=do_request, cost_of=cost_of(kind))
    if raw.status >= 400:
        raise XError(f"{path} -> HTTP {raw.status}: {raw.body[:400]!r}")
    return raw


def _send(path: str, params: dict) -> tuple[int, bytes]:
    """The only function that talks to X (replaced in tests). GET only: this client never writes."""
    import requests
    for attempt in range(10):
        r = requests.get(BASE + path, params={k: v for k, v in params.items() if not k.startswith("_")},
                         headers={"Authorization": f"Bearer {_token()}", "User-Agent": "xrf-research/0.1"},
                         timeout=90)
        if r.status_code == 429:
            reset = int(r.headers.get("x-rate-limit-reset", time.time() + 60))
            time.sleep(max(2, min(900, reset - time.time() + 2)))
            continue
        if r.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        if path.startswith("/tweets/search/all"):
            time.sleep(1.05)          # 1 request/second limit
        return r.status_code, r.content
    raise XError(f"giving up on {path} after retries")


def paginate(conn, path: str, params: dict, *, budget: str, kind: str, max_pages: int = 10_000,
             token_param: str = "next_token") -> Iterator[rawstore.Raw]:
    params = dict(params)
    for _ in range(max_pages):
        raw = get(conn, path, params, budget=budget, kind=kind, n=int(params.get("max_results", 100)))
        yield raw
        nxt = (raw.json().get("meta") or {}).get("next_token")
        if not nxt:
            return
        params[token_param] = nxt


def search_all(conn, query: str, start_time: str, end_time: str, *, budget: str, kind: str = "full",
               max_results: int | None = None, max_pages: int = 10_000, sort_order: str = "recency",
               tag: str | None = None) -> Iterator[rawstore.Raw]:
    """Full-archive search. Collection uses `from:<handle> -is:retweet -is:reply` with kind=full."""
    params = {"query": query, "start_time": start_time, "end_time": end_time, "sort_order": sort_order,
              "max_results": max_results or _p().get("search_max_results", 500), **fields(kind)}
    if tag:
        params["_tag"] = tag
    yield from paginate(conn, "/tweets/search/all", params, budget=budget, kind="posts", max_pages=max_pages)


def counts_all(conn, query: str, start_time: str, end_time: str, *, budget: str) -> int:
    params = {"query": query, "start_time": start_time, "end_time": end_time, "granularity": "day"}
    total = 0
    for raw in paginate(conn, "/tweets/counts/all", params, budget=budget, kind="counts_all"):
        total += int((raw.json().get("meta") or {}).get("total_tweet_count", 0))
    return total


def users_by_username(conn, usernames: list[str], *, budget: str) -> list[rawstore.Raw]:
    names = sorted({u.lstrip("@").lower() for u in usernames if u})
    out = []
    for i in range(0, len(names), 100):
        chunk = names[i:i + 100]
        out.append(get(conn, "/users/by", {"usernames": ",".join(chunk),
                                           "user.fields": "id,username,name,description,public_metrics,verified,created_at"},
                       budget=budget, kind="users", n=len(chunk)))
    return out


def users_by_id(conn, ids: list[str], *, budget: str) -> list[rawstore.Raw]:
    ids = sorted(set(ids))
    out = []
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        out.append(get(conn, "/users", {"ids": ",".join(chunk),
                                        "user.fields": "id,username,name,description,public_metrics,verified,created_at"},
                       budget=budget, kind="users", n=len(chunk)))
    return out


def posts_lookup(conn, ids: list[str], *, budget: str, as_of: str) -> list[rawstore.Raw]:
    """Multi-post lookup; deleted posts come back in `errors`. as_of is in the cache key so each
    deletion check is a fresh request."""
    out = []
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        out.append(get(conn, "/tweets", {"ids": ",".join(chunk), **fields("id"), "_as_of": as_of},
                       budget=budget, kind="posts", n=len(chunk)))
    return out


def probe(conn) -> str:
    """One cheap call to confirm which field names the live API accepts (guides say tweet.fields; the
    v2.175 spec says post.fields). Uses the discovery budget; costs about $0.005-0.01."""
    params = {"query": "from:XDevelopers -is:retweet", "max_results": 10, **fields("id")}
    try:
        get(conn, "/tweets/search/recent", params, budget="discovery", kind="posts", n=10)
        return "tweet"
    except XError as e:
        return f"error: {e}"
