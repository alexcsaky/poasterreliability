"""Turn stored raw X responses into rows in `posts` and `users`. Pure function of raw data."""
from __future__ import annotations

import json
import sqlite3

from . import rawstore


def _refs(t: dict) -> list[dict]:
    return t.get("referenced_tweets") or t.get("referenced_posts") or []


def post_kind(t: dict) -> str:
    refs = {r["type"] for r in _refs(t)}
    if "retweeted" in refs or "reposted" in refs:
        return "repost"
    if "replied_to" in refs:
        return "reply"
    if "quoted" in refs:
        return "quote"
    return "original"


def full_text(t: dict) -> str:
    nt = t.get("note_tweet") or t.get("note_post") or {}
    return nt.get("text") or t.get("text") or ""


def _media(t: dict, media_by_key: dict) -> list[dict]:
    keys = (t.get("attachments") or {}).get("media_keys", []) or []
    return [media_by_key[k] for k in keys if k in media_by_key]


def upsert_user(conn: sqlite3.Connection, u: dict, captured_at: str, raw_id: int) -> None:
    pm = u.get("public_metrics", {}) or {}
    conn.execute(
        "INSERT INTO users(user_id,username,name,description,followers,following,tweet_count,verified,created_at,"
        "captured_at,raw_id) VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET "
        "username=excluded.username,name=excluded.name,description=excluded.description,"
        "followers=excluded.followers,following=excluded.following,tweet_count=excluded.tweet_count,"
        "verified=excluded.verified,captured_at=excluded.captured_at,raw_id=excluded.raw_id "
        "WHERE excluded.captured_at >= COALESCE(users.captured_at,'')",
        (u["id"], u.get("username"), u.get("name"), u.get("description"), pm.get("followers_count"),
         pm.get("following_count"), pm.get("tweet_count"), int(bool(u.get("verified"))), u.get("created_at"),
         captured_at, raw_id))


def ingest(conn: sqlite3.Connection, raw: rawstore.Raw, source: str, store_includes_as_posts: bool = False) -> list[str]:
    """Ingest a tweets payload. Returns ids of main posts. Quoted posts are stored inline on the
    quoting post (quoted_text etc.), not as cohort posts."""
    d = raw.json()
    inc = d.get("includes", {}) or {}
    users = {u["id"]: u for u in inc.get("users", []) or []}
    media = {m["media_key"]: m for m in inc.get("media", []) or []}
    inc_tweets = {t["id"]: t for t in (inc.get("tweets") or inc.get("posts") or [])}
    for u in users.values():
        upsert_user(conn, u, raw.requested_at, raw.id)
    data = d.get("data") or []
    if isinstance(data, dict):
        data = [data]
    ids = []
    for t in data:
        if "username" in t:      # a user payload, not tweets
            upsert_user(conn, t, raw.requested_at, raw.id)
            continue
        q = None
        for r in _refs(t):
            if r["type"] == "quoted":
                q = inc_tweets.get(r["id"], {"id": r["id"]})
        pm = t.get("public_metrics", {}) or {}
        author = users.get(t.get("author_id"), {})
        qa = users.get((q or {}).get("author_id"), {})
        conn.execute(
            "INSERT INTO posts(post_id,author_id,author_username,created_at,text,kind,in_reply_to_user_id,"
            "quoted_post_id,quoted_text,quoted_author_id,quoted_author_username,quoted_created_at,media_json,"
            "quoted_media_json,impressions,likes,reposts,replies,quotes,bookmarks,lang,conversation_id,"
            "captured_at,raw_id,source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(post_id) DO UPDATE SET author_username=COALESCE(excluded.author_username,posts.author_username),text=COALESCE(excluded.text,posts.text),kind=COALESCE(excluded.kind,posts.kind),quoted_post_id=COALESCE(excluded.quoted_post_id,posts.quoted_post_id),quoted_text=COALESCE(excluded.quoted_text,posts.quoted_text),quoted_author_id=COALESCE(excluded.quoted_author_id,posts.quoted_author_id),quoted_author_username=COALESCE(excluded.quoted_author_username,posts.quoted_author_username),quoted_created_at=COALESCE(excluded.quoted_created_at,posts.quoted_created_at),media_json=COALESCE(excluded.media_json,posts.media_json),quoted_media_json=COALESCE(excluded.quoted_media_json,posts.quoted_media_json),lang=COALESCE(excluded.lang,posts.lang),conversation_id=COALESCE(excluded.conversation_id,posts.conversation_id),"
            "impressions=excluded.impressions,likes=excluded.likes,reposts=excluded.reposts,replies=excluded.replies,"
            "quotes=excluded.quotes,bookmarks=excluded.bookmarks,"
            "captured_at=CASE WHEN posts.source IN ('collection','daily') THEN posts.captured_at ELSE excluded.captured_at END,"
            "raw_id=CASE WHEN posts.source IN ('collection','daily') THEN posts.raw_id ELSE excluded.raw_id END,"
            "source=CASE WHEN posts.source IN ('collection','daily') THEN posts.source ELSE excluded.source END",
            (t["id"], t.get("author_id"), author.get("username"), t.get("created_at"), full_text(t),
             post_kind(t), t.get("in_reply_to_user_id"),
             (q or {}).get("id"), full_text(q) if q and "text" in q else None, (q or {}).get("author_id"),
             qa.get("username"), (q or {}).get("created_at"),
             json.dumps(_media(t, media)), json.dumps(_media(q, media)) if q else None,
             pm.get("impression_count"), pm.get("like_count"), pm.get("retweet_count", pm.get("repost_count")), pm.get("reply_count"),
             pm.get("quote_count"), pm.get("bookmark_count"), t.get("lang"), t.get("conversation_id"),
             raw.requested_at, raw.id, source))
        ids.append(t["id"])
    conn.commit()
    return ids


def reingest_all(conn: sqlite3.Connection) -> int:
    """Rebuild posts/users from every stored X response (used by `xrf rebuild`)."""
    rows = conn.execute("SELECT id,endpoint,params_json,status,body_path,requested_at FROM raw_responses "
                        "WHERE provider='x' AND status BETWEEN 200 AND 299 ORDER BY id").fetchall()
    n = 0
    for r in rows:
        raw = rawstore.Raw(r["id"], r["status"], rawstore.load_body(r["body_path"]), r["requested_at"], True)
        ep = r["endpoint"]
        if ep == "/tweets":          # deletion checks: do not ingest as posts
            continue
        params = json.loads(r["params_json"])
        source = {"collection": "collection", "daily": "daily"}.get(str(params.get("_tag", "")).split(":")[0], "discovery")
        if ep.startswith("/users") and not ep.endswith("/tweets"):
            source = "users"
        n += len(ingest(conn, raw, source))
    return n
