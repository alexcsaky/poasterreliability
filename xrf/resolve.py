"""Stage 5: resolve claims against the ledger, in code. A language model is used only to match
codenames and loose model names to ledger names (RULES.md section 6); each match is stored with its reason."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone

from . import config, llm
from .ledger import Release, first_signal_time, load_releases, load_signals, norm_name
from .rules import Window, parse_dt, window_for

MATCH_VERSION = "m-v1"
GRACE_NEVER_SHIPPED = timedelta(days=14)
ATTR_NO_WINDOW_DAYS = 180

LAB_WORDS = {
    "openai": ["openai", "gpt", "chatgpt", "sora", "codex", "o3", "o4", "o5", "dall"],
    "anthropic": ["anthropic", "claude", "opus", "sonnet", "haiku"],
    "google_deepmind": ["google", "deepmind", "gemini", "gemma", "veo", "imagen", "nano banana", "nanobanana", "lyria", "genie"],
    "xai": ["xai", "x.ai", "grok"],
    "meta": ["meta", "llama", "facebook"],
    "mistral": ["mistral", "magistral", "codestral", "devstral", "ministral", "voxtral", "le chat"],
    "deepseek": ["deepseek"],
    "alibaba": ["alibaba", "qwen", "wan", "tongyi"],
    "zhipu": ["zhipu", "z.ai", "zai", "glm"],
    "moonshot": ["moonshot", "kimi"],
}


def lab_of(lab_text: str, model_text: str) -> str | None:
    hay = f"{lab_text} {model_text}".lower()
    hits = [lab for lab, words in LAB_WORDS.items() if any(re.search(r"\b" + re.escape(w), hay) for w in words)]
    return hits[0] if len(hits) == 1 else (None if not hits else hits[0])


# ---- name matching ------------------------------------------------------------------------------

MATCH_SYSTEM = """You match a model name, as written in a social media post, to entries in a list of official AI model releases from one lab. You see only the name and the list; you know nothing about the post or about dates.

Return the release_ids the name refers to:
- An exact model, alias or codename: that one release.
- A family or loose reference ("new Gemini", "next Claude", "Grok 5" when only "Grok 5 Fast" and "Grok 5" exist): every release in that family that the name could refer to. A bare family ("new Gemini") matches all releases in the family.
- A version number that is not in the list (e.g. "GPT-7" when the list stops at GPT-6): no match.
- A codename matches only if the list gives that codename for a release.
Return an empty list if nothing matches. Explain in one sentence."""

MATCH_SCHEMA = {"type": "object", "properties": {
    "release_ids": {"type": "array", "items": {"type": "string"}},
    "is_family": {"type": "boolean"},
    "reason": {"type": "string"}},
    "required": ["release_ids", "is_family", "reason"], "additionalProperties": False}


def match_name(conn: sqlite3.Connection, lab: str, model_text: str, releases: list[Release],
               use_llm: bool = True) -> tuple[list[Release], str, str]:
    """Returns (releases, method, reason)."""
    key = norm_name(model_text)
    lab_rel = [r for r in releases if r["lab"] == lab]
    exact = [r for r in lab_rel if key in r.names]
    if exact:
        return exact, "exact", f"'{model_text}' equals a ledger name/alias/codename"
    have = conn.execute("SELECT release_ids,method,reason FROM alias_matches WHERE name_key=? AND lab=?",
                        (key, lab)).fetchone()
    by_id = {r.id: r for r in lab_rel}
    if have:
        ids = [i for i in (have["release_ids"] or "").split(";") if i in by_id]
        return [by_id[i] for i in ids], have["method"], have["reason"]
    if not use_llm or not lab_rel:
        return [], "none", "no exact match" + ("" if lab_rel else "; lab has no ledger rows")
    listing = "\n".join(f"{r.id} | {r['model']} | aliases: {r['aliases']} | codenames: {r['codenames']}"
                        for r in sorted(lab_rel, key=lambda r: r.id))
    content = [{"type": "text", "text": f"LAB: {lab}\nNAME AS WRITTEN: {model_text}\n\nRELEASES:\n{listing}"}]
    out, raw = llm.structured(conn, role="matcher", system=MATCH_SYSTEM, content=content, schema=MATCH_SCHEMA,
                              prompt_version=MATCH_VERSION)
    ids = [i for i in (out or {}).get("release_ids", []) if i in by_id]
    reason = (out or {}).get("reason", "matcher returned no parseable output")
    method = "llm_family" if (out or {}).get("is_family") else "llm"
    conn.execute("INSERT OR REPLACE INTO alias_matches VALUES (?,?,?,?,?,?)",
                 (key, lab, ";".join(ids), method, reason, raw.id))
    conn.commit()
    return [by_id[i] for i in ids], method, reason


# ---- timing -------------------------------------------------------------------------------------

def _in(t: datetime, w: Window, end: datetime) -> bool:
    lo = w.point - timedelta(hours=12) if w.point else w.start
    return lo <= t <= end


def timing_verdict(post_t: datetime, w: Window, end: datetime, rels: list[Release], as_of: datetime) -> tuple[str, Release | None, str]:
    if not rels:
        if as_of > end + GRACE_NEVER_SHIPPED:
            return "incorrect", None, "no matching release in the ledger by window end + 14 days"
        return "open", None, "no matching release yet; window (+14 days) not closed"
    released = [r for r in rels if r.release_time]
    before = [r for r in released if r.release_time < post_t - timedelta(hours=0)]
    after = sorted([r for r in released if r.release_time >= post_t or (w.point and r.release_time >= w.point - timedelta(hours=12))],
                   key=lambda r: r.release_time)
    if before and not after and len(before) == len(rels) and not any(r.preview_time and r.preview_time >= post_t for r in rels):
        return "uncheckable", before[0], "already released before the post (not a forecast)"
    first = after[0] if after else None
    if first and _in(first.release_time, w, end) and (not w.lower or first.release_time >= w.lower):
        return "correct", first, f"released {first.release_time:%Y-%m-%d %H:%M} inside window ending {end:%Y-%m-%d %H:%M}"
    if first and w.lower and first.release_time < w.lower:
        return "partial", first, f"released early ({first.release_time:%Y-%m-%d}), before the stated period began {w.lower:%Y-%m-%d}"
    prev = [r for r in rels if r.preview_time and _in(r.preview_time, w, end) and r.preview_time >= post_t]
    if prev:
        return "partial", prev[0], f"only a tester preview ({prev[0].preview_time:%Y-%m-%d}) inside the window"
    if as_of <= end:
        return "open", None, "window not closed and no release yet"
    if first:
        return "incorrect", first, f"released {first.release_time:%Y-%m-%d}, after window end {end:%Y-%m-%d}"
    if as_of > end + GRACE_NEVER_SHIPPED:
        return "incorrect", None, "not released by window end + 14 days"
    return "open", None, "window closed, never-shipped grace period (14 days) running"


# ---- attributes ---------------------------------------------------------------------------------

def _nums(s: str) -> list[float]:
    s = (s or "").lower().replace(",", "")
    out = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(m\b|k\b|million|thousand)?", s):
        v = float(m.group(1))
        unit = m.group(2) or ""
        if unit.startswith("m"):
            v *= 1_000_000
        elif unit in ("k", "thousand"):
            v *= 1000
        out.append(v)
    return out


def _close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol * max(abs(b), 1e-9)


def attribute_verdict(attr: str, value: str, rel: Release) -> tuple[str, str]:
    name, _, detail = (attr or "").partition(":")
    if name == "name":
        v = norm_name(value)
        if v in rel.names:
            return "correct", f"ledger name/alias matches '{value}'"
        if any(v and (n.startswith(v) or v.startswith(n)) for n in rel.names):
            return "partial", "name matches apart from a suffix"
        return "incorrect", f"ledger name is '{rel['model']}'"
    if name == "context_window":
        if not rel["context_window"]:
            return "uncheckable", "context window not stated by lab"
        lv, cv = _nums(rel["context_window"]), _nums(value)
        if not lv or not cv:
            return "uncheckable", "value not numeric"
        a, b = cv[0], lv[0]
        if a < 10_000 and b >= 10_000:     # "128" meaning 128k
            a *= 1000
        if _close(a, b, 0.0) or {round(a), round(b)} <= {128000, 131072} or {round(a), round(b)} <= {1000000, 1048576} \
                or {round(a), round(b)} <= {200000, 204800}:
            return "correct", f"ledger context window {rel['context_window']}"
        if _close(a, b, 0.10):
            return "partial", f"within 10% of ledger {rel['context_window']}"
        return "incorrect", f"ledger context window {rel['context_window']}"
    if name == "price":
        if not rel["price"]:
            return "uncheckable", "price not stated by lab"
        led = rel["price"].lower()
        part = "output" if "output" in detail.lower() else "input" if "input" in detail.lower() else None
        m = re.search((part or "input") + r"[^$0-9]*\$?\s*(\d+(?:\.\d+)?)", led)
        cv = _nums(value)
        if not m or not cv:
            return "uncheckable", "price not comparable"
        b = float(m.group(1))
        if _close(cv[0], b, 0.0):
            return "correct", f"ledger price {rel['price']}"
        if _close(cv[0], b, 0.10):
            return "partial", f"within 10% of ledger price {rel['price']}"
        return "incorrect", f"ledger price {rel['price']}"
    if name == "benchmark":
        bench = norm_name(detail)
        for pair in (rel["benchmarks"] or "").split(";"):
            if "=" not in pair:
                continue
            bn, bv = pair.split("=", 1)
            nb = norm_name(bn)
            if bench and (bench in nb or nb in bench):
                lv, cv = _nums(bv), _nums(value)
                if not lv or not cv:
                    return "uncheckable", "benchmark value not numeric"
                pct = "%" in bv or lv[0] <= 100
                tol_c, tol_p = (0.5, 2.0) if pct else (0.005 * lv[0], 0.02 * lv[0])
                d = abs(cv[0] - lv[0])
                if d <= tol_c:
                    return "correct", f"lab states {bn.strip()}={bv.strip()}"
                if d <= tol_p:
                    return "partial", f"within 2 points of lab's {bn.strip()}={bv.strip()}"
                return "incorrect", f"lab states {bn.strip()}={bv.strip()}"
        return "uncheckable", f"benchmark '{detail}' not stated by lab"
    if name == "modality":
        return ("correct" if norm_name(value) in norm_name(rel["modality"]) else "incorrect"), f"ledger modality {rel['modality']}"
    if name == "release_route":
        v = value.lower()
        routes = {"api": rel["api_available_at"], "app": rel["consumer_available_at"],
                  "open": rel["open_weights_at"], "weights": rel["open_weights_at"]}
        for k, have in routes.items():
            if k in v:
                return ("correct" if have else "incorrect"), f"ledger {k} date: {have or 'none'}"
        return "uncheckable", "route not recognised"
    return "uncheckable", "attribute not in ledger"


# ---- driver -------------------------------------------------------------------------------------

def claimed_tier(rels: list[Release], model_text: str, lab: str) -> str:
    tiers = {r["tier"] for r in rels}
    if len(tiers) == 1:
        return tiers.pop()
    lines = [l.lower() for l in config.lab_by_id().get(lab, {}).get("flagship_lines", [])]
    if any(norm_name(l.split(" (")[0]) and norm_name(l.split(" (")[0]) in norm_name(model_text) for l in lines):
        return "flagship"
    return "any"


def resolve_all(conn: sqlite3.Connection, run: str = "main", as_of: datetime | None = None,
                use_llm: bool = True) -> dict:
    as_of = as_of or datetime.now(timezone.utc)
    releases = load_releases()
    signals = load_signals()
    by_id = {r.id: r for r in releases}
    conn.execute("DELETE FROM verdicts WHERE claim_id IN (SELECT claim_id FROM claims WHERE run=?)", (run,))
    rows = conn.execute("SELECT * FROM claims WHERE run=? AND valid=1", (run,)).fetchall()
    counts: dict[str, int] = {}

    def put(cid, variant, verdict, rel=None, w=None, end=None, reason="", sig=(None, None, None), tier=None):
        counts[verdict] = counts.get(verdict, 0) + 1
        conn.execute("INSERT OR REPLACE INTO verdicts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (cid, variant, verdict, rel.id if rel else None,
                      w.start.isoformat() if w else None, end.isoformat() if end else None,
                      (rel.urls[0] if rel and rel.urls else None), reason, sig[0], sig[1], sig[2], tier,
                      ((end - w.start).total_seconds() / 86400) if (w and end) else None))

    for c in rows:
        cid = c["claim_id"]
        post_t = parse_dt(c["posted_at"])
        if c["family"] == "uncheckable":
            put(cid, "main", "uncheckable", reason=c["uncheckable_reason"] or "uncheckable")
            continue
        lab = lab_of(c["lab"] or "", c["model_name"] or "")
        if not lab:
            put(cid, "main", "uncheckable", reason="lab not in scope or not identifiable")
            continue
        rels, method, mreason = match_name(conn, lab, c["model_name"], releases, use_llm=use_llm)
        if c["family"] == "timing":
            w = window_for(c["window_phrase"], post_t)
            if w == "unstated":
                put(cid, "main", "uncheckable", reason="no window")
                continue
            if w is None:
                put(cid, "main", "uncheckable", reason=f"window not mappable: {c['window_phrase']!r}")
                continue
            tier = claimed_tier(rels, c["model_name"], lab)
            ends = {"main": w.end, **w.variants} if w.variants else {"main": w.end}
            for variant, end in ends.items():
                v, rel, why = timing_verdict(post_t, w, end, rels, as_of)
                target = rel or (min((r for r in rels if r.release_time and r.release_time >= post_t),
                                     key=lambda r: r.release_time, default=None))
                sig = (None, None, None)
                if target:
                    fs = first_signal_time(target, signals)
                    pre_signals = [parse_dt(s["posted_at"]) for s in signals
                                   if s.get("release_id") == target.id and s.get("posted_at")]
                    pre_signals += [t for t in (target.dt("announced_at"), target.preview_time) if t]
                    before = any(t <= post_t for t in pre_signals)
                    sig = (int(before), (fs - post_t).total_seconds() / 3600 if fs else None,
                           (target.release_time - post_t).total_seconds() / 3600 if target.release_time else None)
                put(cid, variant, v, rel, w, end, f"{why} [match: {method}: {mreason}]", sig, tier)
        elif c["family"] == "attribute":
            attr = c["attribute"] or ""
            if attr.startswith("name"):
                rels2 = [r for r in releases if r["lab"] == lab]
                hit = [r for r in rels2 if norm_name(c["attribute_value"] or "") in r.names]
                w = window_for(c["window_phrase"], post_t)
                end = w.end if isinstance(w, Window) else post_t + timedelta(days=ATTR_NO_WINDOW_DAYS)
                ok = [r for r in hit if r.release_time and post_t <= r.release_time <= end]
                if ok:
                    put(cid, "main", "correct", ok[0], reason=f"lab released '{ok[0]['model']}'")
                elif hit and any(r.release_time and r.release_time < post_t for r in hit):
                    put(cid, "main", "uncheckable", hit[0], reason="name already public before the post")
                elif as_of <= end:
                    put(cid, "main", "open", reason="no release with that name yet")
                else:
                    put(cid, "main", "incorrect", reason="no release with that name by the deadline")
                continue
            released = sorted([r for r in rels if r.release_time], key=lambda r: r.release_time)
            if not released:
                w = window_for(c["window_phrase"], post_t)
                deadline = (w.end + GRACE_NEVER_SHIPPED) if isinstance(w, Window) else post_t + timedelta(days=ATTR_NO_WINDOW_DAYS)
                if as_of > deadline:
                    put(cid, "main", "uncheckable", reason="model never shipped")
                else:
                    put(cid, "main", "open", reason=f"model not released yet [match: {method}: {mreason}]")
                continue
            rel = released[0] if len(released) == 1 else next((r for r in released if norm_name(c["model_name"]) in r.names), released[0])
            v, why = attribute_verdict(attr, c["attribute_value"] or "", rel)
            put(cid, "main", v, rel, reason=f"{why} [match: {method}: {mreason}]")
    conn.commit()
    return counts
