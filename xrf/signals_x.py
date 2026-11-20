"""Official signals posted on X (D-008). Needs the X key; charged to the `x_reads` budget.

For each flagship release in the ledger, search the lab's official accounts and listed staff for posts naming the
model in the 21 days before its first release time. Each hit is an official pre-release signal and is written to
ledger/signals_x.csv (same columns as signals.csv; the resolver reads both). Raw responses are stored as usual,
so the file can be regenerated offline."""
from __future__ import annotations

from datetime import timedelta

from . import config, xapi
from .ledger import SIGNAL_COLUMNS, load_releases, write_csv

LOOKBACK_DAYS = 21


def _accounts(lab_id: str) -> list[str]:
    lab = config.lab_by_id()[lab_id]
    staff = (config.load("lab_staff").get("staff") or {}).get(lab_id) or []
    return sorted({*lab.get("x_accounts", []), *staff}, key=str.lower)


def collect(conn, flagship_only: bool = True, per_release: int = 50, log=print) -> int:
    rows = []
    for r in sorted(load_releases(), key=lambda r: r.id):
        if flagship_only and r["tier"] != "flagship":
            continue
        t = r.release_time or r.preview_time or r.dt("announced_at")
        if not t:
            continue
        names = sorted({r["model"]} | {a.strip() for a in (r["aliases"] or "").split(";") if a.strip()}, key=len)[:4]
        accts = _accounts(r["lab"])
        q = f"({' OR '.join('from:' + a for a in accts)}) ({' OR '.join(chr(34) + n + chr(34) for n in names)}) -is:retweet"
        if len(q) > 1000:
            q = q[:q.rfind(" OR from:", 0, 900)] + ") (" + " OR ".join(f'"{n}"' for n in names) + ") -is:retweet"
        s = (t - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        e = t.strftime("%Y-%m-%dT%H:%M:%SZ")
        n = 0
        for raw in xapi.search_all(conn, q, s, e, budget="x_reads", kind="sweep", max_results=per_release,
                                   max_pages=1, sort_order="recency", tag=f"signals:{r.id}"):
            d = raw.json()
            for i, p in enumerate(d.get("data") or []):
                author = p.get("author_id")
                handle = next((u["username"] for u in (d.get("includes") or {}).get("users", []) if u["id"] == author), None)
                rows.append({"signal_id": f"{r.id}-x{p['id']}", "release_id": r.id, "lab": r["lab"],
                             "model_ref": r["model"], "signal_type": "teaser", "posted_at": p["created_at"],
                             "author": f"@{handle}" if handle else f"user {author}", "text": (p.get("text") or "")[:280],
                             "url": f"https://x.com/{handle or 'i'}/status/{p['id']}",
                             "notes": "official account or listed staff on X, found by xrf signals-x"})
                n += 1
        log(f"  {r.id}: {n} official X posts in the {LOOKBACK_DAYS} days before release")
    write_csv(config.LEDGER / "signals_x.csv", rows, SIGNAL_COLUMNS)
    return len(rows)
