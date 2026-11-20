"""Stage 1 check: independent re-research of a random 20% of ledger rows.

`sample` writes ledger/reresearch/sample.csv with only release_id, lab and model (what the second researcher
is given). The second researcher fills the same fields in ledger/reresearch/second_pass.csv from official
sources without seeing the first pass. `compare` reports field-level disagreement."""
from __future__ import annotations

import csv
import random
import re
from datetime import timedelta

from . import config, state
from .ledger import load_releases, read_csv, write_csv
from .rules import parse_dt

DIR = config.LEDGER / "reresearch"
DATE_FIELDS = ["announced_at", "consumer_available_at", "api_available_at", "open_weights_at", "preview_at"]
OTHER_FIELDS = ["status", "price", "context_window", "benchmarks"]
SEED = 20261120


def sample(share: float = 0.2) -> list[dict]:
    rels = sorted(load_releases(), key=lambda r: r.id)
    k = max(1, round(share * len(rels)))
    pick = random.Random(SEED).sample(rels, k)
    rows = [{"release_id": r.id, "lab": r["lab"], "model": r["model"]} for r in sorted(pick, key=lambda r: r.id)]
    write_csv(DIR / "sample.csv", rows, ["release_id", "lab", "model"])
    return rows


def _day(s):
    try:
        d = parse_dt(s)
    except ValueError:
        return "?"
    return d.date().isoformat() if d else ""


def _nums(s):
    return sorted(round(float(x), 2) for x in re.findall(r"\d+(?:\.\d+)?", (s or "").replace(",", "")))


def _bench(s):
    out = {}
    for pair in (s or "").split(";"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            n = re.findall(r"\d+(?:\.\d+)?", v)
            if n:
                out[re.sub(r"[^a-z0-9]", "", k.lower())] = float(n[0])
    return out


def field_agree(f: str, a: str, b: str) -> tuple[bool | None, str]:
    """Returns (agree, kind). agree None = both blank (not compared)."""
    a, b = (a or "").strip(), (b or "").strip()
    if not a and not b:
        return None, "both blank"
    if not a or not b:
        return False, "one blank"
    if f in DATE_FIELDS:
        da, db_ = parse_dt(a), parse_dt(b)
        if not da or not db_:
            return False, "unparseable"
        return abs(da.date() - db_.date()) <= timedelta(days=0), f"{_day(a)} vs {_day(b)}"
    if f == "status":
        return a == b, f"{a} vs {b}"
    if f == "context_window":
        na, nb = _nums(a), _nums(b)
        return bool(na and nb and abs(na[0] - nb[0]) <= 0.02 * max(na[0], nb[0])), f"{a} vs {b}"
    if f == "price":
        return _nums(a) == _nums(b), f"{a} vs {b}"
    if f == "benchmarks":
        ba, bb = _bench(a), _bench(b)
        common = set(ba) & set(bb)
        if not common:
            return None, "no benchmark in common"
        bad = [k for k in common if abs(ba[k] - bb[k]) > 0.15]
        return not bad, f"{len(common)} in common, {len(bad)} differ"
    return a == b, ""


def compare() -> dict:
    first = {r.id: r.row for r in load_releases()}
    second = read_csv(DIR / "second_pass.csv")
    lines = ["# Ledger re-research check", "",
             f"A random {len(second)} of {len(first)} ledger rows (seed {SEED}) were researched again from official "
             "sources by researchers who saw only the lab and model name. Fields compared at day level (dates), "
             "exact numbers (price), 2% (context window), 0.15 points (benchmarks in common).", "",
             "| release_id | field | first pass | second pass | result |", "|---|---|---|---|---|"]
    n_cmp = n_bad = 0
    rows_bad = set()
    per_field: dict[str, list[int]] = {}
    for s in second:
        f0 = first.get(s["release_id"])
        if not f0:
            continue
        for f in DATE_FIELDS + OTHER_FIELDS:
            ok, kind = field_agree(f, f0.get(f, ""), s.get(f, ""))
            if ok is None:
                continue
            n_cmp += 1
            per_field.setdefault(f, [0, 0])
            per_field[f][0] += 1
            if not ok:
                n_bad += 1
                per_field[f][1] += 1
                rows_bad.add(s["release_id"])
                lines.append(f"| {s['release_id']} | {f} | {f0.get(f, '')} | {s.get(f, '')} | {kind} |")
    lines += ["", "## Summary", "", "| field | compared | disagree |", "|---|---|---|"]
    lines += [f"| {f} | {v[0]} | {v[1]} |" for f, v in per_field.items()]
    res = {"share": len(second) / max(1, len(first)), "rows": len(second), "fields": n_cmp,
           "field_disagreement": n_bad / n_cmp if n_cmp else 0.0,
           "row_disagreement": len(rows_bad) / len(second) if second else 0.0}
    lines += ["", f"Field-level disagreement: {n_bad}/{n_cmp} = {res['field_disagreement']:.1%}. "
                  f"Rows with any disagreement: {len(rows_bad)}/{len(second)} = {res['row_disagreement']:.1%}.", ""]
    (DIR / "report.md").write_text("\n".join(lines), encoding="utf-8")
    state.set("ledger_reresearch", res)
    return res
