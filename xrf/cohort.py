"""Stage 2: candidate pool, inclusion floor, ranking, pilot subset.

Budget: everything here is charged to the `discovery` budget (75 USD cap).

Steps
  1. sweeps   - full-archive keyword search around each ledger release in the 90-day window
                (posts only, no user objects), plus a generic release-talk sweep.
  2. pool     - authors of sweep posts, accounts they quote, accounts they @mention; plus Grok X search
                suggestions if XAI_API_KEY is set (discovery only: it adds names, never data).
  3. lookup   - user objects for pool members seen at least `min_sightings` times (users cost 0.01 USD).
  4. floor    - exclude official lab accounts and lab staff; require >= 5,000 followers; count
                release-related original posts in the last 90 days (counts endpoint, 0.01 USD per call);
                require >= 10.
  5. rank     - read up to `impression_sample` most recent release-related original posts per
                passing account (aged >= 3 days so impression counts have settled), take the median
                impression_count; ties and missing impressions fall back to follower count.
"""
from __future__ import annotations

import json
import random
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from . import config, xapi, xparse
from .ledger import load_releases, write_csv

BUDGET = "discovery"
WINDOW_DAYS = 90
SETTLE_DAYS = 3
FOLLOWER_FLOOR = 5000
POST_FLOOR = 10

# Release-related filter used for cohort counting and ranking (deterministic keyword rule, D-010).
FAMILY_TERMS = ["GPT", "ChatGPT", "OpenAI", "Sora", "Codex", "Claude", "Anthropic", "Opus", "Sonnet", "Haiku",
                "Fable", "Mythos", "Gemini", "Gemma", "DeepMind", "Veo", "\"Nano Banana\"", "Grok", "xAI", "Llama",
                "Meta AI", "Mistral", "Magistral", "Devstral", "DeepSeek", "Qwen", "Kimi", "Moonshot", "GLM",
                "Zhipu", "\"Z.ai\""]
RELEASE_TERMS = ["release", "released", "releasing", "launch", "launched", "launching", "ship", "ships",
                 "shipping", "drop", "drops", "dropping", "coming", "soon", "announce", "announced", "leak",
                 "leaked", "rumor", "rumour", "\"next week\"", "\"this week\"", "today", "tomorrow", "imminent",
                 "codename", "preview", "benchmark", "pricing", "\"context window\"", "available", "rolling",
                 "out now", "new model"]


def release_query(prefix: str = "") -> str:
    q = f"{prefix} ({' OR '.join(FAMILY_TERMS)}) ({' OR '.join(RELEASE_TERMS)}) -is:retweet -is:reply"
    return re.sub(r"\s+", " ", q).strip()


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def window(as_of: datetime) -> tuple[datetime, datetime]:
    return as_of - timedelta(days=WINDOW_DAYS), as_of


# ---- 1. sweeps ----------------------------------------------------------------------------------

def sweep(conn: sqlite3.Connection, as_of: datetime, pages_per_release: int = 1, per_page: int = 100,
          generic_pages: int = 10, log=print) -> int:
    start, end = window(as_of)
    rels = [r for r in load_releases() if (r.dt("announced_at") or r.release_time)
            and start - timedelta(days=7) <= (r.dt("announced_at") or r.release_time) <= end]
    n = 0
    for r in sorted(rels, key=lambda r: r.id):
        t0 = r.dt("announced_at") or r.release_time
        names = xapi.ordered_terms({r["model"]} | {a.split("(")[0].strip() for a in (r["aliases"] or "").split(";") if a.strip()}
                                   | {c.split("(")[0].strip() for c in (r["codenames"] or "").split(";") if c.strip()})[:6]
        q = "(" + " OR ".join(f'"{x}"' for x in names if x) + ") -is:retweet -is:reply"
        s, e = max(start, t0 - timedelta(days=7)), min(end, t0 + timedelta(days=2))
        if s >= e:
            continue
        for raw in xapi.search_all(conn, q, _iso(s), _iso(e), budget=BUDGET, kind="sweep", max_results=per_page,
                                   max_pages=pages_per_release, sort_order="relevancy", tag=f"sweep:{r.id}"):
            ids = xparse.ingest(conn, raw, "discovery")
            _add_pool(conn, raw, f"sweep:{r.id}")
            n += len(ids)
        log(f"  sweep {r.id}: total posts so far {n}")
    for raw in xapi.search_all(conn, release_query(), _iso(start), _iso(end - timedelta(days=SETTLE_DAYS)),
                               budget=BUDGET, kind="sweep", max_results=500, max_pages=generic_pages,
                               sort_order="relevancy", tag="sweep:generic"):
        n += len(xparse.ingest(conn, raw, "discovery"))
        _add_pool(conn, raw, "sweep:generic")
    return n


def _add_pool(conn, raw, source: str) -> None:
    d = raw.json()
    inc = {t["id"]: t for t in ((d.get("includes") or {}).get("tweets") or (d.get("includes") or {}).get("posts") or [])}
    for t in d.get("data") or []:
        _pool_add(conn, t.get("author_id"), None, source)
        for r in xparse._refs(t):
            if r["type"] == "quoted" and r["id"] in inc:
                _pool_add(conn, inc[r["id"]].get("author_id"), None, "quoted")
        for m in ((t.get("entities") or {}).get("mentions") or []):
            _pool_add(conn, m.get("id"), m.get("username"), "mentioned")
    conn.commit()


def _pool_add(conn, user_id, username, source) -> None:
    if not user_id and not username:
        return
    key = user_id or f"@{username.lower()}"
    row = conn.execute("SELECT sources FROM candidates WHERE user_id=?", (key,)).fetchone()
    if row:
        conn.execute("UPDATE candidates SET sources=? WHERE user_id=?", (row[0] + ";" + source, key))
    else:
        conn.execute("INSERT INTO candidates VALUES (?,?,?,?)",
                     (key, username, source, datetime.now(timezone.utc).isoformat(timespec="seconds")))


# ---- 2b. Grok discovery (optional) --------------------------------------------------------------

def grok_discover(conn, as_of: datetime, log=print) -> list[str]:
    import os
    from . import state, xai
    offline = os.environ.get("XRF_OFFLINE") == "1"
    if offline and not state.get("grok_used"):
        return []
    if not offline and not config.env_key("XAI_API_KEY"):
        log("  XAI_API_KEY not set: skipping Grok discovery")
        return []
    names = xai.discover_accounts(conn, as_of)
    if not offline:
        state.set("grok_used", True)
    for u in names:
        _pool_add(conn, None, u, "grok")
    conn.commit()
    return names


# ---- 3. lookup ----------------------------------------------------------------------------------

def lookup_pool(conn, min_sightings: int = 2, max_users: int = 1500, log=print) -> int:
    rows = conn.execute("SELECT user_id, username, sources FROM candidates").fetchall()
    scored = []
    for r in rows:
        srcs = r["sources"].split(";")
        forced = "grok" in srcs
        if len(srcs) >= min_sightings or forced:
            scored.append((len(srcs) + (100 if forced else 0), r))
    scored.sort(key=lambda x: -x[0])
    scored = scored[:max_users]
    ids = [r["user_id"] for _, r in scored if not r["user_id"].startswith("@")]
    names = [r["user_id"][1:] for _, r in scored if r["user_id"].startswith("@")]
    have = {x[0] for x in conn.execute("SELECT user_id FROM users")}
    have_names = {(x[0] or "").lower() for x in conn.execute("SELECT username FROM users")}
    ids = [i for i in ids if i not in have]
    names = [n for n in names if n not in have_names]
    for raw in xapi.users_by_id(conn, ids, budget=BUDGET) + xapi.users_by_username(conn, names, budget=BUDGET):
        xparse.ingest(conn, raw, "users")
    log(f"  looked up {len(ids)} ids + {len(names)} usernames")
    return len(ids) + len(names)


# ---- 4. floor and exclusions --------------------------------------------------------------------

def official_handles() -> set[str]:
    out = set()
    for lab in config.labs():
        out |= {h.lower() for h in lab.get("x_accounts", [])}
    staff = config.load("lab_staff") or {}
    for lab_id, handles in (staff.get("staff") or {}).items():
        out |= {h.lower() for h in handles or []}
    return out


STAFF_RX = re.compile(
    r"\b(?:@?(openai|anthropicai|anthropic|googledeepmind|deepmind|google|xai|aiatmeta|meta|mistralai|mistral|"
    r"deepseek_ai|deepseek|alibaba_qwen|qwen|alibaba|zai_org|zhipu|kimi_moonshot|moonshot))\b", re.I)
STAFF_CTX = re.compile(r"\b(at|@|working on|work on|member of technical staff|mts|engineer|researcher|research|"
                       r"lead|head of|pm|product|team|building|scientist|cto|ceo|founder|cofounder|co-founder|dev rel|devrel)\b", re.I)
EX_RX = re.compile(r"\b(ex|former|formerly|prev|previously|alum)\b", re.I)


def staff_flag(desc: str) -> str | None:
    """Heuristic: bio says the person works at a covered lab. 'ex-'/'former' bios are not excluded."""
    if not desc:
        return None
    for m in STAFF_RX.finditer(desc):
        ctx = desc[max(0, m.start() - 40): m.end() + 10]
        if EX_RX.search(ctx):
            continue
        if STAFF_CTX.search(ctx):
            return f"bio suggests lab staff: '{ctx.strip()}'"
    return None


def apply_floor(conn, as_of: datetime, log=print) -> tuple[list[dict], list[dict]]:
    start, end = window(as_of)
    off = official_handles()
    pool_ids = {r[0] for r in conn.execute("SELECT user_id FROM candidates")}
    users = conn.execute("SELECT * FROM users").fetchall()
    keep, excluded = [], []
    for u in users:
        if u["user_id"] not in pool_ids and f"@{(u['username'] or '').lower()}" not in pool_ids:
            continue
        uname = (u["username"] or "").lower()
        base = {"user_id": u["user_id"], "username": u["username"], "followers": u["followers"]}
        if uname in off:
            excluded.append({**base, "reason": "official lab account or listed lab staff (config)"})
            continue
        sf = staff_flag(u["description"] or "")
        if sf:
            excluded.append({**base, "reason": sf})
            continue
        if (u["followers"] or 0) < FOLLOWER_FLOOR:
            excluded.append({**base, "reason": f"followers {u['followers']} < {FOLLOWER_FLOOR}"})
            continue
        keep.append(dict(u))
    passed = []
    for u in sorted(keep, key=lambda u: -(u["followers"] or 0)):
        n = xapi.counts_all(conn, release_query(f"from:{u['username']}"), _iso(start), _iso(end), budget=BUDGET)
        base = {"user_id": u["user_id"], "username": u["username"], "followers": u["followers"]}
        if n < POST_FLOOR:
            excluded.append({**base, "reason": f"release-related original posts in 90 days {n} < {POST_FLOOR}"})
        else:
            passed.append({**u, "release_posts_90d": n})
    log(f"  floor: {len(passed)} pass, {len(excluded)} excluded")
    return passed, excluded


# ---- 5. rank ------------------------------------------------------------------------------------

def rank(conn, passed: list[dict], as_of: datetime, impression_sample: int = 20, log=print) -> list[dict]:
    start, end = window(as_of)
    end_settled = end - timedelta(days=SETTLE_DAYS)
    out = []
    for u in passed:
        imps = []
        for raw in xapi.search_all(conn, release_query(f"from:{u['username']}"), _iso(start), _iso(end_settled),
                                   budget=BUDGET, kind="rank", max_results=max(10, impression_sample),
                                   max_pages=1, sort_order="recency", tag=f"rank:{u['username']}"):
            for t in raw.json().get("data") or []:
                if xparse.post_kind(t) in ("original", "quote"):
                    v = (t.get("public_metrics") or {}).get("impression_count")
                    if v is not None:
                        imps.append(v)
        out.append({**u, "median_impressions": statistics.median(imps) if imps else None,
                    "impression_posts": len(imps)})
    have_imp = any(r["median_impressions"] is not None for r in out)
    out.sort(key=lambda r: ((r["median_impressions"] or -1) if have_imp else 0, r["followers"] or 0), reverse=True)
    for i, r in enumerate(out, 1):
        r["rank"] = i
        r["rank_basis"] = "median_impressions" if r["median_impressions"] is not None else "followers (no impressions)"
    return out


COHORT_COLUMNS = ["rank", "username", "user_id", "followers", "release_posts_90d", "median_impressions",
                  "impression_posts", "rank_basis", "sources", "pilot", "pilot_third"]


def pilot_subset(ranked: list[dict], n_per_third: int = 5, seed: int = 20261119) -> list[dict]:
    k = len(ranked)
    thirds = [ranked[: k // 3], ranked[k // 3: 2 * k // 3], ranked[2 * k // 3:]]
    rng = random.Random(seed)
    out = []
    for name, group in zip(("top", "middle", "bottom"), thirds):
        pick = rng.sample(group, min(n_per_third, len(group)))
        for p in pick:
            p["pilot"] = 1
            p["pilot_third"] = name
            out.append(p)
    return out


def build(conn, as_of: datetime | None = None, top_n: int = 100, log=print) -> dict:
    as_of = as_of or datetime.now(timezone.utc)
    log("Stage 2: sweeps")
    sweep(conn, as_of, log=log)
    grok_discover(conn, as_of, log=log)
    log("Stage 2: lookups")
    lookup_pool(conn, log=log)
    passed, excluded = apply_floor(conn, as_of, log=log)
    ranked = rank(conn, passed, as_of, log=log)[:top_n]
    srcs = {r["user_id"]: r["sources"] for r in conn.execute("SELECT user_id, sources FROM candidates")}
    for r in ranked:
        s = Counter((srcs.get(r["user_id"]) or srcs.get("@" + (r["username"] or "").lower()) or "").split(";"))
        r["sources"] = "; ".join(f"{k}x{v}" for k, v in s.most_common(5))
    pilot = pilot_subset(ranked)
    write_csv(config.COHORT / "cohort.csv", ranked, COHORT_COLUMNS)
    write_csv(config.COHORT / "excluded.csv", excluded, ["username", "user_id", "followers", "reason"])
    write_csv(config.COHORT / "pilot.csv", pilot, COHORT_COLUMNS)
    return {"pool": conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0], "passed": len(passed),
            "cohort": len(ranked), "excluded": len(excluded), "pilot": [p["username"] for p in pilot]}
