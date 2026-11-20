"""A tiny fake X API and fake LLM for end-to-end tests. Synthetic accounts and posts only."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

USERS = {
    "1": dict(id="1", username="alice", name="Alice", description="AI watcher", public_metrics={"followers_count": 50000}),
    "2": dict(id="2", username="bob", name="Bob", description="leaks & rumours", public_metrics={"followers_count": 20000}),
    "3": dict(id="3", username="carol", name="Carol", description="newsletter", public_metrics={"followers_count": 8000}),
    "4": dict(id="4", username="dave", name="Dave", description="small", public_metrics={"followers_count": 3000}),
    "5": dict(id="5", username="eve", name="Eve", description="Member of technical staff at @OpenAI", public_metrics={"followers_count": 90000}),
    "6": dict(id="6", username="OpenAI", name="OpenAI", description="", public_metrics={"followers_count": 9000000}),
}


def P(pid, uid, t, text, kind="original", quoted=None, imps=1000):
    d = {"id": pid, "author_id": uid, "created_at": t, "text": text,
         "public_metrics": {"impression_count": imps, "like_count": 1, "retweet_count": 0, "reply_count": 0, "quote_count": 0}}
    if kind == "reply":
        d["referenced_tweets"] = [{"type": "replied_to", "id": "999"}]
    if quoted:
        d["referenced_tweets"] = [{"type": "quoted", "id": quoted}]
    return d


POSTS = [
    P("101", "1", "2026-10-01T10:00:00.000Z", "GPT-9 drops next week, trust me", imps=50000),
    P("102", "1", "2026-10-12T09:00:00.000Z", "Gemini 9 this week", imps=40000),
    P("103", "1", "2026-10-13T09:00:00.000Z", "Nice weather today"),
    P("104", "1", "2026-10-14T09:00:00.000Z", "lol replying", kind="reply"),
    P("201", "2", "2026-10-02T10:00:00.000Z", "GPT-9 will have a 2M context window", imps=20000),
    P("202", "2", "2026-10-03T10:00:00.000Z", "Huge things coming from OpenAI, cooking", imps=30000),
    P("203", "2", "2026-10-08T10:00:00.000Z", "GPT-9 vibes are immaculate", imps=25000),
    P("301", "3", "2026-10-15T10:00:00.000Z", "Per @alice, Gemini 9 soon", quoted="102", imps=9000),
    P("302", "3", "2026-11-12T08:00:00.000Z", "Gemini 10 maybe next month?", imps=9000),
    P("303", "3", "2026-11-13T08:00:00.000Z", "GPT-10 today", imps=9000),
    P("401", "4", "2026-10-05T10:00:00.000Z", "GPT-9 soon", imps=100),
    P("501", "5", "2026-10-06T10:00:00.000Z", "GPT-9 next week", imps=100000),
]
BY_ID = {p["id"]: p for p in POSTS}
DELETED = {"201"}          # for deletion checks

calls = {"x": 0, "llm": 0}


def _t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _payload(posts, with_users=True):
    inc_t = [BY_ID[r["id"]] for p in posts for r in p.get("referenced_tweets", []) if r["type"] == "quoted" and r["id"] in BY_ID]
    d = {"data": posts, "meta": {"result_count": len(posts)}}
    inc = {}
    if inc_t:
        inc["tweets"] = inc_t
    if with_users:
        uids = {p["author_id"] for p in posts + inc_t}
        inc["users"] = [USERS[u] for u in sorted(uids)]
    if inc:
        d["includes"] = inc
    if not posts:
        d.pop("data")
    return d


def x_send(path, params):
    calls["x"] += 1
    if path in ("/tweets/search/all", "/tweets/search/recent"):
        q = params["query"]
        s, e = _t(params["start_time"]), _t(params["end_time"])
        m = re.search(r"from:(\w+)", q)
        uid = next((u for u, d in USERS.items() if m and d["username"].lower() == m.group(1).lower()), None)
        posts = [p for p in POSTS if s <= _t(p["created_at"]) < e and (uid is None or p["author_id"] == uid)]
        if "-is:reply" in q:
            posts = [p for p in posts if not any(r["type"] == "replied_to" for r in p.get("referenced_tweets", []))]
        if not m:   # sweeps: posts naming a model
            posts = [p for p in posts if re.search(r"GPT|Gemini", p["text"])]
        posts = sorted(posts, key=lambda p: p["created_at"], reverse=True)
        return 200, json.dumps(_payload(posts, with_users="author_id" in params.get("expansions", "") and "users" not in path)).encode()
    if path == "/tweets/counts/all":
        m = re.search(r"from:(\w+)", params["query"])
        n = {"alice": 30, "bob": 15, "carol": 12, "dave": 40, "eve": 50}.get(m.group(1).lower(), 0) if m else 0
        return 200, json.dumps({"data": [], "meta": {"total_tweet_count": n}}).encode()
    if path == "/users":
        ids = params["ids"].split(",")
        return 200, json.dumps({"data": [USERS[i] for i in ids if i in USERS]}).encode()
    if path == "/users/by":
        names = params["usernames"].lower().split(",")
        return 200, json.dumps({"data": [u for u in USERS.values() if u["username"].lower() in names]}).encode()
    if path == "/tweets":
        ids = params["ids"].split(",")
        data = [{"id": i, "author_id": BY_ID[i]["author_id"], "created_at": BY_ID[i]["created_at"]} for i in ids if i in BY_ID and i not in DELETED]
        errs = [{"resource_id": i, "title": "Not Found Error"} for i in ids if i in DELETED or i not in BY_ID]
        return 200, json.dumps({"data": data, "errors": errs}).encode()
    return 404, b'{"title":"not found"}'


# ---- fake LLM -----------------------------------------------------------------------------------

def S(text, src="post_text"):
    return {"source": src, "text": text, "image_index": -1, "region": ""}


E = S("")


def claim(family, model, lab, window=None, attr=None, hedge=("flat", None), origin=("original", "", None), cspan=None):
    return {
        "family": family, "claim_span": S(cspan), "lab": {"value": lab[0], "span": S(lab[1]) if lab[1] else E},
        "model": {"value": model, "span": S(model)},
        "window": {"stated": bool(window), "phrase": window or "unstated", "span": S(window) if window else E},
        "attribute": attr or {"name": "none", "detail": "", "value": "", "span": E},
        "hedge": {"level": hedge[0], "span": S(hedge[1] or cspan)},
        "origin": {"type": origin[0], "relayed_account": origin[1], "span": S(origin[2]) if origin[2] else E},
        "evidence": {"offered": "none", "span": E},
    }


CANNED = {
    "GPT-9 drops next week, trust me": {"claims": [claim("timing", "GPT-9", ("OpenAI", "GPT-9"), "next week", cspan="GPT-9 drops next week")], "uncheckable_reason": "none"},
    "Gemini 9 this week": {"claims": [claim("timing", "Gemini 9", ("Google", "Gemini 9"), "this week", cspan="Gemini 9 this week")], "uncheckable_reason": "none"},
    "GPT-9 will have a 2M context window": {"claims": [claim("attribute", "GPT-9", ("OpenAI", "GPT-9"), attr={"name": "context_window", "detail": "", "value": "2M", "span": S("2M context window")}, cspan="GPT-9 will have a 2M context window")], "uncheckable_reason": "none"},
    "Huge things coming from OpenAI, cooking": {"claims": [], "uncheckable_reason": "pure_hype"},
    "Per @alice, Gemini 9 soon": {"claims": [claim("timing", "Gemini 9", ("Google", "Gemini 9"), "soon", origin=("relay", "@alice", "Per @alice"), cspan="Gemini 9 soon")], "uncheckable_reason": "none"},
    "Gemini 10 maybe next month?": {"claims": [claim("timing", "Gemini 10", ("Google", "Gemini 10"), "next month", hedge=("question", "?"), cspan="Gemini 10 maybe next month?")], "uncheckable_reason": "none"},
    "GPT-10 today": {"claims": [claim("timing", "GPT-10", ("OpenAI", "GPT-10"), "today", cspan="GPT-10 today")], "uncheckable_reason": "none"},
    # invented span -> must be rejected by the validator
    "GPT-9 soon": {"claims": [claim("timing", "GPT-9", ("OpenAI", "GPT-9"), "tomorrow", cspan="GPT-9 soon")], "uncheckable_reason": "none"},
    "GPT-9 next week": {"claims": [claim("timing", "GPT-9", ("OpenAI", "GPT-9"), "next week", cspan="GPT-9 next week")], "uncheckable_reason": "none"},
}


def _msg(model, obj):
    return json.dumps({"id": "msg_x", "type": "message", "role": "assistant", "model": model,
                       "content": [{"type": "text", "text": json.dumps(obj)}], "stop_reason": "end_turn",
                       "usage": {"input_tokens": 800, "output_tokens": 200}}).encode()


def llm_send(model, system, content, schema, mcfg):
    calls["llm"] += 1
    text = content[0]["text"]
    props = schema["properties"]
    if "about_release" in props:
        m = re.search(r"POST TEXT.*?<<<\n(.*?)\n>>>", text, re.S)
        t = m.group(1) if m else ""
        return 200, _msg(model, {"about_release": bool(re.search(r"GPT|Gemini|OpenAI", t)), "reason": "fake"})
    if "claims" in props:
        m = re.search(r"POST TEXT.*?<<<\n(.*?)\n>>>", text, re.S)
        return 200, _msg(model, CANNED.get(m.group(1), {"claims": [], "uncheckable_reason": "other"}))
    if "release_ids" in props:
        name = re.search(r"NAME AS WRITTEN: (.*)", text).group(1).strip().lower()
        ids = re.findall(r"^(\S+) \| ([^|]+) \|", text, re.M)
        hits = [i for i, n in ids if n.strip().lower().startswith(name)]
        return 200, _msg(model, {"release_ids": hits, "is_family": len(hits) > 1, "reason": "fake prefix match"})
    raise AssertionError("unknown schema")
