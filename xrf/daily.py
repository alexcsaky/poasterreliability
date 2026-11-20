"""Stage 9: prospective capture (built and tested; NOT scheduled - scheduling is Alex's call).

`daily(day)`: pull the cohort's original and quote posts for one UTC day, run pass 1 and pass 2 the same
day, write prospective/claims/<day>.jsonl, append its SHA-256 to prospective/HASHES.txt and commit both.
Once the repo (or just HASHES.txt) is public, the commit is a timestamp showing the claims were logged
before outcomes were known.

`deletion_check(today)`: re-request claim-bearing posts 7 and 30 days after capture; record any gone.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date, datetime, time, timedelta, timezone

from . import collect, config, extract, xapi


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    s = datetime.combine(day, time(0), tzinfo=timezone.utc)
    return s, s + timedelta(days=1)


def claims_file(conn, day: date) -> tuple[str, int]:
    s, e = _day_bounds(day)
    rows = conn.execute("""SELECT c.claim_id, c.post_id, c.account, c.posted_at, c.family, c.lab, c.model_name,
                                  c.window_phrase, c.attribute, c.attribute_value, c.hedge, c.origin, c.relayed_account,
                                  c.evidence, c.uncheckable_reason, c.claim_span, c.model AS extractor, c.prompt_version
                           FROM claims c WHERE c.run='main' AND c.valid=1 AND c.posted_at>=? AND c.posted_at<?
                           ORDER BY c.posted_at, c.claim_id""",
                        (s.strftime("%Y-%m-%dT%H:%M:%S"), e.strftime("%Y-%m-%dT%H:%M:%S"))).fetchall()
    lines = [json.dumps(dict(r), ensure_ascii=False, sort_keys=True) for r in rows]
    return "\n".join(lines) + ("\n" if lines else ""), len(lines)


def daily(conn, day: date, usernames: list[str], commit: bool = True, log=print) -> dict:
    s, e = _day_bounds(day)
    n_posts = 0
    for u in usernames:
        n_posts += collect.collect_account(conn, u, s, e, tag="daily")
    authors = [r[0] for r in conn.execute(
        f"SELECT user_id FROM users WHERE lower(username) IN ({','.join('?' * len(usernames))})",
        [u.lower() for u in usernames])]
    ex = extract.run_all(conn, authors, s.strftime("%Y-%m-%dT%H:%M:%S"), e.strftime("%Y-%m-%dT%H:%M:%S"), log=log)
    body, n = claims_file(conn, day)
    out_dir = config.PROSPECTIVE / "claims"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{day.isoformat()}.jsonl"
    path.write_text(body, encoding="utf-8")
    sha = hashlib.sha256(body.encode()).hexdigest()
    hashes = config.PROSPECTIVE / "HASHES.txt"
    line = f"{day.isoformat()} {sha} claims={n} logged_at={datetime.now(timezone.utc).isoformat(timespec='seconds')}\n"
    existing = hashes.read_text() if hashes.exists() else ""
    if not any(l.startswith(day.isoformat() + " " + sha) for l in existing.splitlines()):
        with open(hashes, "a", encoding="utf-8") as f:
            f.write(line)
    committed = False
    if commit:
        subprocess.run(["git", "-C", str(config.ROOT), "add", str(path), str(hashes)], check=True)
        r = subprocess.run(["git", "-C", str(config.ROOT), "commit", "-m", f"daily claims {day.isoformat()} sha256 {sha}"],
                           capture_output=True, text=True)
        committed = r.returncode == 0
    return {"day": day.isoformat(), "posts": n_posts, **ex, "claims_logged": n, "sha256": sha, "committed": committed}


def deletion_check(conn, today: date, days=(7, 30), log=print) -> dict:
    out = {}
    for d in days:
        cutoff = (datetime.combine(today, time(0), tzinfo=timezone.utc) - timedelta(days=d)).isoformat()
        rows = conn.execute("""SELECT DISTINCT p.post_id FROM posts p JOIN claims c ON c.post_id=p.post_id AND c.valid=1
                               WHERE p.captured_at <= ? AND p.post_id NOT IN
                               (SELECT post_id FROM deletion_checks WHERE check_day=?)""", (cutoff, d)).fetchall()
        ids = [r[0] for r in rows]
        gone = 0
        for raw in xapi.posts_lookup(conn, ids, budget="x_reads", as_of=f"{today.isoformat()}:d{d}") if ids else []:
            j = raw.json()
            present = {t["id"] for t in j.get("data") or []}
            errs = {e.get("resource_id") or e.get("value"): e for e in j.get("errors") or []}
            asked = json.loads(conn.execute("SELECT params_json FROM raw_responses WHERE id=?", (raw.id,)).fetchone()[0])["ids"].split(",")
            for pid in asked:
                exists = pid in present
                gone += not exists
                detail = "" if exists else json.dumps(errs.get(pid, {"title": "missing"}))
                conn.execute("INSERT OR REPLACE INTO deletion_checks VALUES (?,?,?,?,?,?)",
                             (pid, d, raw.requested_at, int(exists), detail, raw.id))
        conn.commit()
        out[f"day{d}"] = {"checked": len(ids), "gone": gone}
        log(f"  deletion check {d}d: {len(ids)} checked, {gone} gone")
    return out
