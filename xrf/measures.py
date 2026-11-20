"""Stage 6: per-account measures. Pure function of the DB and the ledger."""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np

from .ledger import load_releases, norm_name
from .rules import parse_dt

LEDGER_START = datetime(2025, 12, 1, tzinfo=timezone.utc)
MIN_RANKED = 20
SCORED_HEDGES = ("flat", "hedged")
RESOLVED = ("correct", "incorrect", "partial")


def wilson(k: float, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


# ---- baseline -----------------------------------------------------------------------------------

class Baseline:
    def __init__(self, releases=None):
        self.rel = [(r["lab"], r["tier"], r.release_time) for r in (releases or load_releases()) if r.release_time]

    def p(self, lab: str | None, tier: str, w_days: float, post_t: datetime) -> float | None:
        """Share of rolling windows of length w in the 12 months before the post (truncated at the ledger
        start) in which `lab` (any lab if None) released a model of `tier` (any tier if 'any')."""
        lo = max(post_t - timedelta(days=365), LEDGER_START)
        w = timedelta(days=max(w_days, 1 / 24))
        last_start = post_t - w
        if last_start <= lo:
            return None
        times = sorted(t for (l, ti, t) in self.rel
                       if (lab is None or l == lab) and (tier in ("any", None) or ti == tier) and lo <= t < post_t)
        starts = np.arange(0, (last_start - lo).total_seconds(), 86400.0)
        if len(starts) == 0:
            return None
        ts = np.array([(t - lo).total_seconds() for t in times])
        if len(ts) == 0:
            return 0.0
        idx = np.searchsorted(ts, starts, side="left")
        nxt = np.where(idx < len(ts), ts[np.minimum(idx, len(ts) - 1)], np.inf)
        hit = nxt < starts + w.total_seconds()
        return float(hit.mean())


# ---- shrinkage ----------------------------------------------------------------------------------

def fit_beta_binomial(ks: list[float], ns: list[int]) -> tuple[float, float] | None:
    from scipy.optimize import minimize
    from scipy.special import betaln
    data = [(k, n) for k, n in zip(ks, ns) if n > 0]
    if len(data) < 3:
        return None
    k = np.array([d[0] for d in data], float)
    n = np.array([d[1] for d in data], float)

    def nll(x):
        a, b = math.exp(x[0]), math.exp(x[1])
        return -float(np.sum(betaln(k + a, n - k + b) - betaln(a, b)))

    m = max(1e-3, min(1 - 1e-3, k.sum() / n.sum()))
    best = None
    for s in (2.0, 10.0, 50.0):
        r = minimize(nll, [math.log(m * s), math.log((1 - m) * s)], method="Nelder-Mead",
                     options={"maxiter": 2000, "xatol": 1e-6, "fatol": 1e-8})
        if best is None or r.fun < best.fun:
            best = r
    a, b = math.exp(best.x[0]), math.exp(best.x[1])
    return (a, b) if a + b < 1e6 else (a, b)


# ---- clustering for originality -----------------------------------------------------------------

def originators(rows: list[dict]) -> dict[str, bool]:
    """rows: timing claims with keys claim_id, account, posted_at, target, start, end, origin.
    Cluster by same target and overlapping window; the earliest post in a cluster is the originator,
    unless it credits another account (a relay)."""
    by_target = defaultdict(list)
    for r in rows:
        by_target[r["target"]].append(r)
    out = {}
    for _, group in by_target.items():
        group.sort(key=lambda r: r["start"])
        clusters, cur, cur_end = [], [], None
        for r in group:
            if cur and r["start"] <= cur_end:
                cur.append(r)
                cur_end = max(cur_end, r["end"])
            else:
                if cur:
                    clusters.append(cur)
                cur, cur_end = [r], r["end"]
        if cur:
            clusters.append(cur)
        for c in clusters:
            first = min(c, key=lambda r: r["posted_at"])
            for r in c:
                out[r["claim_id"]] = (r is first) and r["origin"] != "relay"
    return out


# ---- main ---------------------------------------------------------------------------------------

def compute(conn, run: str = "main", accounts: list[str] | None = None) -> dict:
    base = Baseline()
    q = """SELECT c.*, v.verdict, v.release_id, v.window_start, v.window_end, v.signal_before_post,
                  v.hours_post_to_first_signal, v.hours_post_to_release, v.claimed_tier, v.window_days
           FROM claims c LEFT JOIN verdicts v ON v.claim_id=c.claim_id AND v.variant='main'
           WHERE c.run=? AND c.valid=1"""
    claims = [dict(r) for r in conn.execute(q, (run,))]
    soon = {(r["claim_id"], r["variant"]): r["verdict"] for r in
            conn.execute("SELECT claim_id, variant, verdict FROM verdicts WHERE variant LIKE 'soon%'")}
    if accounts is None:
        accounts = sorted({r[0] for r in conn.execute(
            "SELECT DISTINCT author_username FROM posts WHERE source IN ('collection','daily')")})
    from .resolve import lab_of

    # originality over timing claims with a target
    orig_rows = []
    for c in claims:
        if c["family"] == "timing" and c["window_start"] and c["window_end"]:
            tgt = c["release_id"] or f"{lab_of(c['lab'] or '', c['model_name'] or '')}:{norm_name(c['model_name'])}"
            orig_rows.append({"claim_id": c["claim_id"], "account": c["account"], "posted_at": c["posted_at"],
                              "target": tgt, "start": c["window_start"], "end": c["window_end"], "origin": c["origin"]})
    is_orig = originators(orig_rows)

    per = {}
    for acc in accounts:
        posts = conn.execute("SELECT post_id FROM posts WHERE author_username=? AND kind IN ('original','quote') "
                             "AND source IN ('collection','daily')", (acc,)).fetchall()
        pids = [p[0] for p in posts]
        rel_posts = [r[0] for r in conn.execute(
            f"SELECT post_id FROM pass1 WHERE about_release=1 AND post_id IN ({','.join('?' * len(pids))})", pids)] if pids else []
        ac = [c for c in claims if c["account"] == acc]
        checkable_posts = {c["post_id"] for c in ac if c["family"] in ("timing", "attribute") and c["hedge"] in SCORED_HEDGES}
        rejected_posts = {r[0] for r in conn.execute(
            "SELECT post_id FROM extractions WHERE run=? AND uncheckable_reason IN ('extraction_rejected','extraction_failed')", (run,))}
        rel_set = set(rel_posts)
        vague_den = len(rel_set - rejected_posts)
        vague_num = len((rel_set - rejected_posts) - checkable_posts)

        def acc_stats(rows, label):
            res = [r for r in rows if r["verdict"] in RESOLVED]
            n = len(res)
            k = sum(1 for r in res if r["verdict"] == "correct")
            lo, hi = wilson(k, n)
            d = {f"{label}_n": n, f"{label}_correct": k,
                 f"{label}_partial": sum(1 for r in res if r["verdict"] == "partial"),
                 f"{label}_acc": (k / n) if n else None, f"{label}_lo": lo, f"{label}_hi": hi,
                 f"{label}_open": sum(1 for r in rows if r["verdict"] == "open")}
            return d, res

        scored = [c for c in ac if c["hedge"] in SCORED_HEDGES]
        timing = [c for c in scored if c["family"] == "timing"]
        attr = [c for c in scored if c["family"] == "attribute"]
        row = {"account": acc, "posts": len(pids), "release_posts": len(rel_set),
               "checkable_claims": len(timing) + len(attr), "question_or_joke_claims": sum(1 for c in ac if c["hedge"] in ("question", "joke")),
               "vagueness_rate": (vague_num / vague_den) if vague_den else None, "vagueness_n": vague_den}
        d, t_res = acc_stats(timing, "timing")
        row.update(d)
        row.update(acc_stats(attr, "attr")[0])
        pre = [c for c in timing if c["signal_before_post"] == 0]
        d, pre_res = acc_stats(pre, "pre")
        row.update(d)
        for h in SCORED_HEDGES:
            row.update(acc_stats([c for c in timing if c["hedge"] == h], f"timing_{h}")[0])
        for label, res in (("timing", t_res), ("pre", pre_res)):
            ps = []
            for c in res:
                lab = lab_of(c["lab"] or "", c["model_name"] or "")
                p = base.p(lab, c["claimed_tier"] or "any", c["window_days"] or 1, parse_dt(c["posted_at"]))
                if p is not None:
                    ps.append(p)
            mb = statistics.mean(ps) if ps else None
            row[f"{label}_baseline"] = mb
            row[f"{label}_skill"] = (row[f"{label}_acc"] - mb) if (mb is not None and row[f"{label}_acc"] is not None) else None
        leads = [c["hours_post_to_release"] for c in t_res if c["verdict"] == "correct" and c["hours_post_to_release"] is not None]
        row["median_lead_hours"] = statistics.median(leads) if leads else None
        row["lead_n"] = len(leads)
        ot = [c for c in timing if c["claim_id"] in is_orig]
        row["original_share"] = (sum(1 for c in ot if is_orig[c["claim_id"]]) / len(ot)) if ot else None
        row["original_n"] = len(ot)
        row["relay_share"] = (sum(1 for c in timing if c["origin"] == "relay") / len(timing)) if timing else None
        for s in ("soon7", "soon14", "soon30"):
            vs = [soon.get((c["claim_id"], s)) for c in timing]
            vs = [v for v in vs if v in RESOLVED]
            row[f"{s}_n"] = len(vs)
            row[f"{s}_acc"] = (sum(v == "correct" for v in vs) / len(vs)) if vs else None
        row["resolved_n"] = row["timing_n"] + row["attr_n"]
        row["resolved_correct"] = row["timing_correct"] + row["attr_correct"]
        per[acc] = row

    rows = list(per.values())
    fit = fit_beta_binomial([r["resolved_correct"] for r in rows], [r["resolved_n"] for r in rows])
    fit_pre = fit_beta_binomial([r["pre_correct"] for r in rows], [r["pre_n"] for r in rows])
    for r in rows:
        if fit:
            a, b = fit
            r["shrunk_acc"] = (r["resolved_correct"] + a) / (r["resolved_n"] + a + b) if r["resolved_n"] else a / (a + b)
        else:
            r["shrunk_acc"] = None
        if fit_pre:
            a, b = fit_pre
            r["shrunk_pre_acc"] = (r["pre_correct"] + a) / (r["pre_n"] + a + b) if r["pre_n"] else a / (a + b)
        else:
            r["shrunk_pre_acc"] = None
        r["ranked"] = int(r["resolved_n"] >= MIN_RANKED)
    ranked = sorted([r for r in rows if r["ranked"] and r["shrunk_acc"] is not None], key=lambda r: -r["shrunk_acc"])
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return {"accounts": rows, "fit": fit, "fit_pre": fit_pre}
