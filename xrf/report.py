"""Stage 8: report/pilot.md, generated entirely from the DB, the ledger and config."""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone

from . import audit, config, costs, state
from .ledger import load_releases, load_signals


def _f(x, pct=False, nd=2):
    if x is None:
        return "–"
    if pct:
        return f"{100 * x:.0f}%"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def _table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _ci(acc, lo, hi, n):
    return "–" if not n else f"{100 * acc:.0f}% ({100 * lo:.0f}–{100 * hi:.0f}), n={n}"


def estimate(conn, m: dict) -> dict:
    """Costed estimate for the full cohort, from observed pilot rates where available."""
    px = config.load("pricing")
    p = px["x"]
    am = px["anthropic"]["models"]
    mc = config.load("models")
    pilot = state.get("pilot_accounts") or []
    days = 90
    obs_posts = conn.execute("SELECT COUNT(*) FROM posts WHERE source='collection'").fetchone()[0]
    quoted = conn.execute("SELECT COUNT(*) FROM posts WHERE source='collection' AND quoted_post_id IS NOT NULL").fetchone()[0]
    if obs_posts and pilot:
        ppd = obs_posts / len(pilot) / days
        basis = f"observed: {obs_posts} posts from {len(pilot)} pilot accounts over {days} days"
    else:
        ppd = 8.0
        basis = "ASSUMED 8 original+quote posts per account per day (no pilot data yet)"
    qshare = (quoted / obs_posts) if obs_posts else 0.3
    rel = conn.execute("SELECT AVG(about_release) FROM pass1").fetchone()[0]
    rel_share = rel if rel is not None else 0.35
    spent_llm = conn.execute("SELECT COALESCE(SUM(usd),0), COUNT(*) FROM cost_events WHERE budget='model_calls' AND endpoint='messages'").fetchone()

    def llm_cost(model, tin, tout):
        return tin * am[model]["input_per_mtok_usd"] / 1e6 + tout * am[model]["output_per_mtok_usd"] / 1e6

    p1 = llm_cost(mc["pass1"]["model"], 900, 150)
    p2 = llm_cost(mc["pass2"]["model"], 3000, 2000)
    out = {"basis": basis, "posts_per_account_day": ppd, "quoted_share": qshare, "release_share": rel_share,
           "pass1_usd_per_post": p1, "pass2_usd_per_release_post": p2}
    for label, d in (("100 accounts x 90 days", 90), ("100 accounts x 12 months", 365)):
        posts = 100 * ppd * d
        x_low = posts * p["post_read_usd"]
        x_high = posts * (1 + qshare) * p["post_read_usd"] + (posts / 500) * 2 * p["user_read_usd"]
        llm = posts * p1 + posts * rel_share * p2
        out[label] = {"posts": posts, "x_usd_low": x_low, "x_usd_high": x_high, "llm_usd": llm,
                      "total_low": x_low + llm, "total_high": x_high + llm}
    return out


def build(conn, m: dict, as_of: datetime, audit_scores: dict | None = None) -> str:
    rel = load_releases()
    sig = load_signals()
    rows = sorted(m["accounts"], key=lambda r: (r.get("rank") or 999, -(r["resolved_n"] or 0)))
    L = []
    L.append("# Pilot report: X release-forecaster tracker")
    L.append("")
    L.append(f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by `python -m xrf rebuild`; verdicts as of "
             f"{as_of:%Y-%m-%d %H:%M UTC}. Every figure below is regenerated from stored raw API responses, the ledger "
             "and `RULES.md` (tag `rules-v1`). Nothing here is published; the repo is private.")
    L.append("")
    L.append("> **Backtest caveat.** A backtest only sees posts that still existed when collected. Posts deleted "
             "before collection (plausibly the wrong ones) are missing, so **every accuracy figure in this report is an "
             "upper bound**.")
    L.append("")
    n_posts = conn.execute("SELECT COUNT(*) FROM posts WHERE source IN ('collection','daily') AND kind IN ('original','quote')").fetchone()[0]
    if n_posts == 0:
        L.append("> **No pilot data yet.** No posts have been collected, so the yield, measures and audit sections are "
                 "empty. See `docs/STATUS.md` for what is blocking collection.")
        L.append("")

    # ledger
    L.append("## Ground truth")
    L.append("")
    by_lab = {}
    for r in rel:
        by_lab.setdefault(r["lab"], [0, 0])
        by_lab[r["lab"]][0] += 1
        by_lab[r["lab"]][1] += r["tier"] == "flagship"
    L.append(f"`ledger/releases.csv`: {len(rel)} release events (1 Dec 2025 to {as_of:%d %b %Y}); "
             f"`ledger/signals.csv`: {len(sig)} official pre-release signals.")
    L.append("")
    L.append(_table(["lab", "releases", "flagship"], [[k, v[0], v[1]] for k, v in sorted(by_lab.items())]))
    rr = state.get("ledger_reresearch")
    if rr:
        L.append("")
        L.append(f"Independent re-research of a random {rr['share']:.0%} of rows ({rr['rows']} rows, {rr['fields']} "
                 f"fields compared): field-level disagreement rate **{rr['field_disagreement']:.1%}**; rows with at least "
                 f"one disagreement {rr['row_disagreement']:.1%}. Details: `ledger/reresearch/report.md`.")
    L.append("")

    # yield
    L.append("## Yield")
    L.append("")
    yrows = []
    for r in sorted(rows, key=lambda r: r["account"]):
        yrows.append([f"@{r['account']}", r["posts"], r["release_posts"], r["checkable_claims"], r["resolved_n"],
                      r["timing_open"] + r["attr_open"]])
    tot = [sum(int(x[i]) for x in yrows) for i in range(1, 6)] if yrows else [0] * 5
    yrows.append(["**total**", *tot])
    L.append(_table(["account", "posts", "release-related", "checkable claims", "resolved", "open"], yrows))
    L.append("")
    ex = dict(conn.execute("SELECT COALESCE(uncheckable_reason,'has checkable claim'), COUNT(*) FROM extractions "
                           "WHERE run='main' GROUP BY 1").fetchall())
    if ex:
        L.append("Release-related posts by extraction outcome: " + ", ".join(f"{k}: {v}" for k, v in sorted(ex.items())) + ".")
        L.append("")

    # measures
    L.append("## Measures")
    L.append("")
    L.append("Headline: timing accuracy on claims made **before any official signal** for the model (signals = "
             "`ledger/signals.csv` plus the lab's own announcement and preview dates). Flat and hedged claims only; "
             "questions and jokes are excluded. Partial verdicts count as not correct. Intervals are 95% Wilson. "
             f"Accounts with fewer than 20 resolved claims are listed but not ranked. Shrunk estimates use a "
             f"beta-binomial fitted on the cohort (fit: {m['fit'] and tuple(round(x, 2) for x in m['fit'])}).")
    L.append("")
    hdr = ["rank", "account", "pre-signal timing acc", "skill vs base (pre)", "all timing acc", "skill vs base",
           "attribute acc", "shrunk acc", "median lead (h)", "original share", "vagueness"]
    L.append(_table(hdr, [[r.get("rank") or "–", f"@{r['account']}",
                           _ci(r["pre_acc"], r["pre_lo"], r["pre_hi"], r["pre_n"]),
                           _f(r["pre_skill"]),
                           _ci(r["timing_acc"], r["timing_lo"], r["timing_hi"], r["timing_n"]),
                           _f(r["timing_skill"]),
                           _ci(r["attr_acc"], r["attr_lo"], r["attr_hi"], r["attr_n"]),
                           _f(r["shrunk_acc"], pct=True) + f" (n={r['resolved_n']})",
                           f"{_f(r['median_lead_hours'], nd=0)} (n={r['lead_n']})",
                           f"{_f(r['original_share'], pct=True)} (n={r['original_n']})",
                           f"{_f(r['vagueness_rate'], pct=True)} (n={r['vagueness_n']})"] for r in rows]))
    L.append("")
    L.append("Flat vs hedged timing claims, and the 'soon' sensitivity (7/14/30 days; 14 is used above):")
    L.append("")
    L.append(_table(["account", "flat", "hedged", "soon@7", "soon@14", "soon@30"],
                    [[f"@{r['account']}", _ci(r["timing_flat_acc"], r["timing_flat_lo"], r["timing_flat_hi"], r["timing_flat_n"]),
                      _ci(r["timing_hedged_acc"], r["timing_hedged_lo"], r["timing_hedged_hi"], r["timing_hedged_n"]),
                      f"{_f(r['soon7_acc'], pct=True)} (n={r['soon7_n']})", f"{_f(r['soon14_acc'], pct=True)} (n={r['soon14_n']})",
                      f"{_f(r['soon30_acc'], pct=True)} (n={r['soon30_n']})"] for r in rows]))
    L.append("")

    # audit
    L.append("## Audit")
    L.append("")
    ag = audit.agreement(conn) if (config.AUDIT / "sample.csv").exists() else None
    if ag and ag["posts_compared"]:
        L.append(f"Pass 2 re-run with `{config.load('models')['audit_alt']['model']}` on the {ag['posts_compared']} "
                 f"release-related posts in the audit sample: claim-level F1 **{_f(ag['claim_f1'])}** "
                 f"({ag['claims_matched']} matched, {ag['main_only']} main only, {ag['alt_only']} alt only); post-level "
                 f"agreement on 'has a checkable claim' {_f(ag['post_agreement'], pct=True)}, Cohen's kappa {_f(ag['post_kappa'])}.")
    else:
        L.append("Second-model agreement: not yet run (no sample).")
    if audit_scores:
        a1, a2 = audit_scores["pass1"], audit_scores["pass2"]
        L.append("")
        L.append(f"Human marking ({audit_scores['marked_posts']} posts): pass 1 precision {_f(a1['precision'])}, recall "
                 f"{_f(a1['recall'])}; pass 2 precision {_f(a2['precision'])} (exact fields {_f(a2['precision_exact'])}), "
                 f"recall {_f(a2['recall'])}.")
    else:
        L.append("")
        L.append("Human marking of `audit/sample.csv`: not done yet (precision/recall come from `python -m xrf audit-score`).")
    L.append("")

    # costs
    L.append("## Costs against caps")
    L.append("")
    L.append(_table(["budget", "spent (USD)", "cap (USD)", "remaining"],
                    [[s["budget"], f"{s['spent_usd']:.2f}", f"{s['cap_usd']:.0f}", f"{s['remaining_usd']:.2f}"]
                     for s in costs.summary(conn)]))
    L.append("")
    L.append("X spend is recorded on the worst-case assumption that objects returned through expansions are billed "
             "(the docs do not say); reconcile against the X developer console.")
    L.append("")
    est = estimate(conn, m)
    L.append("### Estimate for the full cohort")
    L.append("")
    L.append(f"Basis: {est['basis']}; quoted share {est['quoted_share']:.0%}; release-related share "
             f"{est['release_share']:.0%}; pass 1 ≈ ${est['pass1_usd_per_post']:.5f}/post, pass 2 ≈ "
             f"${est['pass2_usd_per_release_post']:.3f}/release-related post.")
    L.append("")
    L.append(_table(["scope", "posts", "X reads (USD)", "model calls (USD)", "total (USD)"],
                    [[k, f"{v['posts']:,.0f}", f"{v['x_usd_low']:,.0f}–{v['x_usd_high']:,.0f}", f"{v['llm_usd']:,.0f}",
                      f"{v['total_low']:,.0f}–{v['total_high']:,.0f}"]
                     for k, v in est.items() if isinstance(v, dict)]))
    L.append("")
    L.append("Excludes cohort discovery (already paid once) and the daily job's deletion checks "
             "(about $0.005 per claim-bearing post per check). X caps post reads at 3M a month.")
    L.append("")

    # what broke
    L.append("## What broke")
    L.append("")
    wb = config.REPORT / "what_broke.md"
    L.append(wb.read_text(encoding="utf-8").strip() if wb.exists() else "Nothing recorded.")
    rej = conn.execute("SELECT COUNT(*) FROM claims WHERE run='main' AND valid=0").fetchone()[0]
    unm = conn.execute("SELECT COUNT(*) FROM verdicts WHERE reason LIKE 'window not mappable%'").fetchone()[0]
    L.append("")
    L.append(f"Automatic counts: {rej} extracted claims rejected by the span validator; {unm} timing claims with a "
             "window phrase the rules could not map.")
    L.append("")
    return "\n".join(L) + "\n"
