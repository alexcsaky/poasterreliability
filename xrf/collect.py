"""Stage 3: exhaustive collection for the pilot accounts.

For each account: every original and quote post in the window, via full-archive search
`from:<handle> -is:retweet -is:reply` (the user-timeline endpoint stops at the 800 most recent posts when
replies are excluded, which a prolific account can exceed in 90 days; D-003). Quoted posts' text, authors
and media come through expansions. Capture time = the time the raw response was received."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import xapi, xparse

BUDGET = "x_reads"


def collect_account(conn, username: str, start: datetime, end: datetime, tag: str = "collection") -> int:
    q = f"from:{username} -is:retweet -is:reply"
    n = 0
    for raw in xapi.search_all(conn, q, start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                               budget=BUDGET, kind="full", sort_order="recency", tag=f"{tag}:{username}"):
        n += len(xparse.ingest(conn, raw, tag))
    return n


def collect(conn, usernames: list[str], as_of: datetime | None = None, days: int = 90, log=print) -> dict:
    as_of = as_of or datetime.now(timezone.utc)
    start = as_of - timedelta(days=days)
    out = {}
    for u in usernames:
        out[u] = collect_account(conn, u, start, as_of)
        log(f"  collected @{u}: {out[u]} posts")
    return out
