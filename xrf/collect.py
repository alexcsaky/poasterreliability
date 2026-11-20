"""Stage 3: exhaustive collection for the pilot accounts.

For each account: every original and quote post in the window, via full-archive search
`from:<handle> -is:retweet -is:reply` (the user-timeline endpoint stops at the 800 most recent posts when
replies are excluded, which a prolific account can exceed in 90 days; D-003). Quoted posts' text, authors
and media come through expansions. Capture time = the time the raw response was received."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import costs, state, xapi, xparse

BUDGET = "x_reads"


def collect_account(conn, username: str, start: datetime, end: datetime, tag: str = "collection") -> int:
    q = f"from:{username} -is:retweet -is:reply"
    n = 0
    for raw in xapi.search_all(conn, q, start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                               budget=BUDGET, kind="full", sort_order="recency", tag=f"{tag}:{username}"):
        n += len(xparse.ingest(conn, raw, tag))
    return n


def projected_cost(conn, username: str, start: datetime, end: datetime) -> tuple[int, float]:
    """Count the account's original+quote posts in the window (counts endpoint, ~0.01 USD per 31 days) and
    return (posts, worst-case USD to collect them, assuming every post quotes another and expansions are billed)."""
    n = xapi.counts_all(conn, f"from:{username} -is:retweet -is:reply", start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        end.strftime("%Y-%m-%dT%H:%M:%SZ"), budget=BUDGET)
    p = costs.pricing("x")
    per = p["post_read_usd"] * (2 if p.get("bill_expanded_posts") else 1)
    pages = max(1, -(-n // int(p.get("search_max_results", 500))))
    users = pages * 2 * p["user_read_usd"] if p.get("bill_expanded_users") else 0
    return n, n * per + users


def collect(conn, usernames: list[str], as_of: datetime | None = None, days: int = 90, log=print) -> dict:
    """Collect accounts whole or not at all: an account whose worst-case cost does not fit in the remaining
    x_reads budget is skipped (and recorded), so no account is left partially collected."""
    as_of = as_of or datetime.now(timezone.utc)
    start = as_of - timedelta(days=days)
    out, skipped = {}, {}
    for u in usernames:
        n, usd = projected_cost(conn, u, start, as_of)
        done = conn.execute("SELECT COUNT(*) FROM posts WHERE lower(author_username)=? AND source='collection'",
                            (u.lower(),)).fetchone()[0]
        remaining = costs.caps()[BUDGET] - costs.spent(conn, BUDGET)
        if not done and usd > remaining:
            skipped[u] = {"posts": n, "worst_case_usd": round(usd, 2), "remaining_usd": round(remaining, 2)}
            log(f"  SKIP @{u}: {n} posts, worst case {usd:.2f} USD > remaining {remaining:.2f} USD")
            continue
        out[u] = collect_account(conn, u, start, as_of)
        log(f"  collected @{u}: {out[u]} posts (counts endpoint said {n})")
    state.set("collection_skipped", skipped)
    return {"collected": out, "skipped": skipped}
