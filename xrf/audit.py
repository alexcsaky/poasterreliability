"""Stage 7: audit pack.

- make_sample: 200 posts stratified across accounts and pass-1 decisions, with the pipeline's output and
  empty columns for a human to mark missed, invented and wrong-field claims.
- score: turns a marked file into precision and recall for pass 1 and pass 2.
- alt_run + agreement: pass 2 a second time with a different model on the sample, and agreement.
"""
from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from . import config, extract
from .ledger import norm_name, write_csv

SAMPLE_COLUMNS = ["post_id", "account", "created_at", "url", "text", "quoted_text", "n_images", "pass1_about_release",
                  "pass1_reason", "pass2_claims", "pass2_uncheckable_reason",
                  # --- human columns ---
                  "h_about_release", "h_n_true_claims", "h_missed", "h_invented", "h_wrong_field", "h_notes"]
HUMAN_HELP = ("h_about_release: y/n. h_n_true_claims: how many checkable claims the post really makes. "
              "h_missed: count of real claims the pipeline did not extract. h_invented: count of extracted claims the "
              "post does not make. h_wrong_field: count of extracted claims that are real but have a wrong field "
              "(model, window, attribute, hedge, origin).")


def _claims_text(conn, post_id: str, run: str) -> str:
    rows = conn.execute("SELECT family, model_name, window_phrase, attribute, attribute_value, hedge, origin, valid, rejection "
                        "FROM claims WHERE post_id=? AND run=? ORDER BY claim_id", (post_id, run)).fetchall()
    parts = []
    for i, r in enumerate(rows, 1):
        s = f"[{i}] {r['family']} | model={r['model_name']} | window={r['window_phrase']}"
        if r["attribute"]:
            s += f" | {r['attribute']}={r['attribute_value']}"
        s += f" | {r['hedge']} | {r['origin']}"
        if not r["valid"]:
            s += f" | REJECTED: {r['rejection']}"
        parts.append(s)
    return "\n".join(parts)


def make_sample(conn, n: int = 200, seed: int = 7, path: Path | None = None) -> list[dict]:
    path = path or config.AUDIT / "sample.csv"
    rows = conn.execute("""SELECT p.*, p1.about_release, p1.reason FROM posts p JOIN pass1 p1 ON p1.post_id=p.post_id
                           WHERE p.kind IN ('original','quote') AND p.source IN ('collection','daily')""").fetchall()
    strata = defaultdict(list)
    for r in rows:
        strata[(r["author_username"], r["about_release"])].append(r)
    rng = random.Random(seed)
    for v in strata.values():
        rng.shuffle(v)
    # Equal share per account, split evenly between pass-1 yes and no; round-robin fill until n.
    keys = sorted(strata, key=lambda k: (str(k[0]), str(k[1])))
    picked = []
    while len(picked) < n and any(strata[k] for k in keys):
        for k in keys:
            if strata[k] and len(picked) < n:
                picked.append(strata[k].pop())
    out = []
    for r in picked:
        ex = conn.execute("SELECT uncheckable_reason FROM extractions WHERE post_id=? AND run='main'", (r["post_id"],)).fetchone()
        out.append({"post_id": r["post_id"], "account": r["author_username"], "created_at": r["created_at"],
                    "url": f"https://x.com/{r['author_username']}/status/{r['post_id']}", "text": r["text"],
                    "quoted_text": r["quoted_text"] or "", "n_images": len(extract._images(r)),
                    "pass1_about_release": r["about_release"], "pass1_reason": r["reason"],
                    "pass2_claims": _claims_text(conn, r["post_id"], "main"),
                    "pass2_uncheckable_reason": ex[0] if ex else ""})
    write_csv(path, out, SAMPLE_COLUMNS)
    (path.parent / "README.md").write_text(
        "# Audit pack\n\n`sample.csv`: fill the `h_` columns.\n\n" + HUMAN_HELP +
        "\n\nThen run `python -m xrf audit-score audit/sample.csv`.\n", encoding="utf-8")
    return out


def _int(x) -> int:
    try:
        return int(str(x).strip() or 0)
    except ValueError:
        return 0


def score(path: Path) -> dict:
    with open(path, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if str(r.get("h_about_release", "")).strip()]
    tp = fp = fn = tn = 0
    for r in rows:
        h = r["h_about_release"].strip().lower().startswith("y")
        p = str(r["pass1_about_release"]).strip() in ("1", "True", "true")
        tp += h and p
        fp += (not h) and p
        fn += h and (not p)
        tn += (not h) and (not p)
    ext = inv = wrong = missed = 0
    for r in rows:
        n_ext = sum(1 for line in r["pass2_claims"].splitlines() if line.startswith("[") and "REJECTED" not in line)
        ext += n_ext
        inv += _int(r["h_invented"])
        wrong += _int(r["h_wrong_field"])
        missed += _int(r["h_missed"])
    real_found = ext - inv
    return {
        "marked_posts": len(rows),
        "pass1": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                  "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None},
        "pass2": {"extracted": ext, "invented": inv, "wrong_field": wrong, "missed": missed,
                  "precision": real_found / ext if ext else None,
                  "precision_exact": (real_found - wrong) / ext if ext else None,
                  "recall": real_found / (real_found + missed) if (real_found + missed) else None},
    }


def alt_run(conn, path: Path | None = None) -> int:
    path = path or config.AUDIT / "sample.csv"
    with open(path, encoding="utf-8", newline="") as f:
        ids = [r["post_id"] for r in csv.DictReader(f)]
    n = 0
    for pid in ids:
        post = conn.execute("SELECT * FROM posts WHERE post_id=?", (pid,)).fetchone()
        if post is None:
            continue
        p1 = conn.execute("SELECT about_release FROM pass1 WHERE post_id=?", (pid,)).fetchone()
        if p1 and p1[0]:
            extract.run_pass2(conn, post, run="audit_alt", role="audit_alt")
            n += 1
    return n


def _key(r) -> tuple:
    return (r["family"], norm_name(r["model_name"]), norm_name(r["window_phrase"] or ""),
            norm_name(r["attribute"] or ""), norm_name(r["attribute_value"] or ""))


def agreement(conn, path: Path | None = None) -> dict:
    """Claim-level F1 between the main and alternate pass-2 runs on sampled release-related posts, and
    post-level agreement (Cohen's kappa) on 'has at least one checkable claim'."""
    path = path or config.AUDIT / "sample.csv"
    with open(path, encoding="utf-8", newline="") as f:
        ids = [r["post_id"] for r in csv.DictReader(f)]
    match = a_only = b_only = 0
    post_a, post_b = [], []
    for pid in ids:
        if not conn.execute("SELECT 1 FROM extractions WHERE post_id=? AND run='audit_alt'", (pid,)).fetchone():
            continue
        get = lambda run: [r for r in conn.execute(
            "SELECT * FROM claims WHERE post_id=? AND run=? AND valid=1 AND family!='uncheckable'", (pid, run))]
        A, B = [_key(r) for r in get("main")], [_key(r) for r in get("audit_alt")]
        Bc = list(B)
        for k in A:
            if k in Bc:
                match += 1
                Bc.remove(k)
            else:
                a_only += 1
        b_only += len(Bc)
        post_a.append(bool(A))
        post_b.append(bool(B))
    n = len(post_a)
    f1 = (2 * match / (2 * match + a_only + b_only)) if (match + a_only + b_only) else None
    kappa = None
    if n:
        po = sum(a == b for a, b in zip(post_a, post_b)) / n
        pa, pb = sum(post_a) / n, sum(post_b) / n
        pe = pa * pb + (1 - pa) * (1 - pb)
        kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    return {"posts_compared": n, "claims_matched": match, "main_only": a_only, "alt_only": b_only,
            "claim_f1": f1, "post_kappa": kappa,
            "post_agreement": (sum(a == b for a, b in zip(post_a, post_b)) / n) if n else None}
