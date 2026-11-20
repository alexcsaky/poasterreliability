"""Stage 4: blind claim extraction.

The extractor sees only the post text, its images, the quoted post and the timestamp. It never sees
the ledger, search results, later posts or any outcome. Every extracted field must carry the exact
span of post text (or the image region) it came from; `validate_claim` rejects any field without one.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

from . import llm

P1_VERSION = "p1-v1"
P2_VERSION = "p2-v1"

P1_SYSTEM = """You label posts from X (Twitter). Decide one thing: is this post about the release of an AI model?

Answer true if the post is about a specific AI model's release, past or upcoming, including: predictions or rumours about when a model will ship; announcements or reactions to a model launching; claims about an upcoming or new model's name, price, context window, specs, benchmark results, availability or release route; teasers and hints about unreleased models; leaks of model names or codenames.

Answer false for: general AI commentary, opinion or news that is not about a model release; using or reviewing a model with no reference to its release or its release-time specs; funding, hiring, policy, chips or company news with no model release content; jokes and memes that do not refer to a particular release.

Judge only from what is in the post, the quoted post and the images. Do not guess at context you cannot see."""

P1_SCHEMA = {
    "type": "object",
    "properties": {
        "about_release": {"type": "boolean"},
        "reason": {"type": "string", "description": "one short sentence"},
    },
    "required": ["about_release", "reason"],
    "additionalProperties": False,
}

P2_SYSTEM = """You extract checkable claims about AI model releases from one X post, for a study of which accounts forecast releases accurately. You see only this post: its text, the post it quotes (if any), its images (if any) and its timestamp. You have no other information and must not use outside knowledge about what actually happened.

Record ONLY what the post commits to. Do not infer, complete or correct anything. Two kinds of claim count:
- timing: a named model or model family will be (or has just been) released within some time window ("GPT-6 next week", "Gemini 4 drops today").
- attribute: a property of a named model: its name, price, context window, a benchmark figure, its modality, or how it is released (API, app, open weights).

One post can contain several claims; give each separately.

For every field, give the span it came from:
- span.source = "post_text" or "quoted_text": span.text must be copied EXACTLY, character for character, from that text (a contiguous substring). Set image_index to -1 and region to "".
- span.source = "image": set image_index (0-based, in the order the images are given), region (where in the image, e.g. "top-left headline"), and span.text = the exact words visible there.

Field rules:
- model.value: the model or model family as written (e.g. "GPT-6", "new Gemini", "Grok 5"). If no model or family is named, there is no checkable claim.
- lab.value: the lab as written or as part of the model name (e.g. "OpenAI", "Gemini" implies Google DeepMind: give the lab name and use the model span). If not determinable from the post, use "unstated" with an empty span (source "post_text", text "").
- window: if the post states a time window ("today", "next week", "Dec 3", "soon", "by end of year"), set stated=true, phrase = the exact words, span = where they occur. If the post states no window, set stated=false, phrase="unstated" and an empty span. NEVER infer a window the post does not state; "is coming" or "is cooking" with no time word is unstated unless the post itself uses a time word.
- attribute (attribute claims only; otherwise name="none", value="", empty span): name is one of name, price, context_window, benchmark, modality, release_route, other; detail names the benchmark or price part (e.g. "SWE-bench Verified", "input price"); value is the stated value as written.
- hedge.level: flat (stated as fact), hedged ("might", "I think", "rumoured", "possibly", "maybe", "allegedly"), question (posed as a question), joke (clearly not serious). span = the hedging words, or the asserted words for flat.
- origin: relay if the post attributes the claim to someone else ("per @x", "hearing from", "reportedly", "according to", "sources say", or quoting another account's claim); otherwise original. For relay give the span of the attribution and relayed_account as written (the @handle or name), or "" if unnamed.
- evidence.offered: what the post offers as evidence (screenshot, code string, leaked UI, link, "trust me"), or "none" with an empty span.
- claim_span: the exact sentence or phrase that makes the claim.

If the post is about a model release but contains no checkable claim, return claims=[] and set uncheckable_reason to one of: no_model_named, no_window (a model is named but no time window and no attribute), pure_hype (excitement or teasing with no concrete commitment), past_release_reaction (only reacting to a release that already happened, with no new claim), other. Otherwise set uncheckable_reason to "none"."""

_SPAN = {
    "type": "object",
    "properties": {
        "source": {"type": "string", "enum": ["post_text", "quoted_text", "image"]},
        "text": {"type": "string"},
        "image_index": {"type": "integer"},
        "region": {"type": "string"},
    },
    "required": ["source", "text", "image_index", "region"],
    "additionalProperties": False,
}
_FIELD = {"type": "object", "properties": {"value": {"type": "string"}, "span": _SPAN},
          "required": ["value", "span"], "additionalProperties": False}

P2_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "family": {"type": "string", "enum": ["timing", "attribute"]},
                "claim_span": _SPAN,
                "lab": _FIELD,
                "model": _FIELD,
                "window": {"type": "object", "properties": {
                    "stated": {"type": "boolean"}, "phrase": {"type": "string"}, "span": _SPAN},
                    "required": ["stated", "phrase", "span"], "additionalProperties": False},
                "attribute": {"type": "object", "properties": {
                    "name": {"type": "string", "enum": ["none", "name", "price", "context_window", "benchmark",
                                                         "modality", "release_route", "other"]},
                    "detail": {"type": "string"}, "value": {"type": "string"}, "span": _SPAN},
                    "required": ["name", "detail", "value", "span"], "additionalProperties": False},
                "hedge": {"type": "object", "properties": {
                    "level": {"type": "string", "enum": ["flat", "hedged", "question", "joke"]}, "span": _SPAN},
                    "required": ["level", "span"], "additionalProperties": False},
                "origin": {"type": "object", "properties": {
                    "type": {"type": "string", "enum": ["original", "relay"]},
                    "relayed_account": {"type": "string"}, "span": _SPAN},
                    "required": ["type", "relayed_account", "span"], "additionalProperties": False},
                "evidence": {"type": "object", "properties": {"offered": {"type": "string"}, "span": _SPAN},
                             "required": ["offered", "span"], "additionalProperties": False},
            },
            "required": ["family", "claim_span", "lab", "model", "window", "attribute", "hedge", "origin", "evidence"],
            "additionalProperties": False,
        }},
        "uncheckable_reason": {"type": "string", "enum": ["none", "no_model_named", "no_window", "pure_hype",
                                                           "past_release_reaction", "other"]},
    },
    "required": ["claims", "uncheckable_reason"],
    "additionalProperties": False,
}


# ---- inputs -------------------------------------------------------------------------------------

def _images(post: sqlite3.Row) -> list[dict]:
    """Images in a fixed order: post images, then quoted-post images. Videos/GIFs use their preview."""
    out = []
    for col, owner in (("media_json", "post"), ("quoted_media_json", "quoted")):
        for m in json.loads(post[col] or "[]") if post[col] else []:
            url = m.get("url") or m.get("preview_image_url")
            if url:
                out.append({"owner": owner, "url": url, "type": m.get("type"), "alt": m.get("alt_text") or ""})
    return out[:8]


def build_content(post: sqlite3.Row) -> list[dict]:
    imgs = _images(post)
    lines = [f"POST by @{post['author_username']} at {post['created_at']} (UTC)",
             "POST TEXT (between the markers):", "<<<", post["text"] or "", ">>>"]
    if post["quoted_post_id"]:
        lines += [f"QUOTED POST by @{post['quoted_author_username'] or 'unknown'}"
                  + (f" at {post['quoted_created_at']}" if post["quoted_created_at"] else ""),
                  "QUOTED TEXT (between the markers):", "<<<", post["quoted_text"] or "[not available]", ">>>"]
    if imgs:
        lines.append(f"{len(imgs)} image(s) follow, in order: " + ", ".join(
            f"image {i} ({im['owner']}{', alt: ' + im['alt'] if im['alt'] else ''})" for i, im in enumerate(imgs)))
    content: list[dict] = [{"type": "text", "text": "\n".join(lines)}]
    for im in imgs:
        content.append({"type": "image", "source": {"type": "url", "url": im["url"]}})
    return content


# ---- validator ----------------------------------------------------------------------------------

def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def check_span(span: dict, post: sqlite3.Row, n_images: int, allow_empty: bool = False) -> str | None:
    src, text = span.get("source"), span.get("text", "")
    if allow_empty and not _ws(text) and src != "image":
        return None
    if src == "image":
        idx = span.get("image_index", -1)
        if not (0 <= idx < n_images):
            return f"image_index {idx} out of range ({n_images} images)"
        if not _ws(span.get("region")) or not _ws(text):
            return "image span needs region and visible text"
        return None
    hay = post["text"] if src == "post_text" else post["quoted_text"] if src == "quoted_text" else None
    if hay is None:
        return f"span source {src} not available"
    if not _ws(text):
        return "empty span"
    if _ws(text) not in _ws(hay):
        return f"span not found verbatim in {src}: {text[:60]!r}"
    return None


def validate_claim(c: dict, post: sqlite3.Row) -> list[str]:
    n_img = len(_images(post))
    errs = []

    def chk(name, span, allow_empty=False):
        e = check_span(span, post, n_img, allow_empty)
        if e:
            errs.append(f"{name}: {e}")

    chk("claim_span", c["claim_span"])
    if not _ws(c["model"]["value"]):
        errs.append("model: empty")
    chk("model", c["model"]["span"])
    if c["lab"]["value"].strip().lower() == "unstated":
        chk("lab", c["lab"]["span"], allow_empty=True)
    else:
        chk("lab", c["lab"]["span"])
    w = c["window"]
    if w["stated"]:
        chk("window", w["span"])
        if _ws(w["phrase"]).lower() not in _ws(w["span"]["text"]).lower():
            errs.append("window: phrase not inside its span")
    else:
        if w["phrase"].strip().lower() != "unstated" or _ws(w["span"]["text"]):
            errs.append("window: stated=false requires phrase 'unstated' and an empty span")
    a = c["attribute"]
    if c["family"] == "attribute":
        if a["name"] == "none" or not _ws(a["value"]):
            errs.append("attribute: attribute claim without attribute name/value")
        chk("attribute", a["span"])
        nums = re.findall(r"\d+(?:\.\d+)?", a["value"])
        if nums and not any(n in _ws(a["span"]["text"]).replace(",", "") for n in nums):
            errs.append("attribute: value's number does not appear in its span")
    chk("hedge", c["hedge"]["span"])
    o = c["origin"]
    if o["type"] == "relay":
        chk("origin", o["span"])
        ra = o["relayed_account"].strip()
        if ra and ra.lstrip("@").lower() not in _ws(o["span"]["text"]).lower() + " " + (post["quoted_author_username"] or "").lower():
            errs.append("origin: relayed_account not in its span")
    ev = c["evidence"]
    if ev["offered"].strip().lower() in ("", "none"):
        if _ws(ev["span"]["text"]):
            errs.append("evidence: 'none' must have an empty span")
    else:
        chk("evidence", ev["span"])
    return errs


# ---- runners ------------------------------------------------------------------------------------

def run_pass1(conn: sqlite3.Connection, post: sqlite3.Row) -> bool | None:
    have = conn.execute("SELECT about_release FROM pass1 WHERE post_id=? AND model=? AND prompt_version=?",
                        (post["post_id"], _model("pass1"), P1_VERSION)).fetchone()
    if have:
        return bool(have[0])
    out, raw = llm.structured(conn, role="pass1", system=P1_SYSTEM, content=build_content(post),
                              schema=P1_SCHEMA, prompt_version=P1_VERSION)
    about = None if out is None else bool(out["about_release"])
    conn.execute("INSERT OR REPLACE INTO pass1 VALUES (?,?,?,?,?,?,?)",
                 (post["post_id"], _model("pass1"), P1_VERSION, None if about is None else int(about),
                  (out or {}).get("reason", "no parseable output"), raw.id, _now()))
    conn.commit()
    return about


def _model(role: str) -> str:
    from . import config
    return config.load("models")[role]["model"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_pass2(conn: sqlite3.Connection, post: sqlite3.Row, run: str = "main", role: str = "pass2") -> int:
    model = _model(role)
    have = conn.execute("SELECT n_claims FROM extractions WHERE post_id=? AND model=? AND prompt_version=? AND run=?",
                        (post["post_id"], model, P2_VERSION, run)).fetchone()
    if have:
        return have[0]
    out, raw = llm.structured(conn, role=role, system=P2_SYSTEM, content=build_content(post),
                              schema=P2_SCHEMA, prompt_version=P2_VERSION)
    return store_extraction(conn, post, out, raw.id, model, run)


def store_extraction(conn, post, out: dict | None, raw_id: int, model: str, run: str) -> int:
    conn.execute("DELETE FROM claims WHERE post_id=? AND run=?", (post["post_id"], run))
    if out is None:
        conn.execute("INSERT OR REPLACE INTO extractions VALUES (?,?,?,?,?,?,?,?,?)",
                     (post["post_id"], model, P2_VERSION, run, raw_id, _now(), 0, 0, "extraction_failed"))
        conn.commit()
        return 0
    n_ok = n_bad = 0
    for i, c in enumerate(out.get("claims", [])):
        errs = validate_claim(c, post)
        family = c["family"]
        unchk = None
        if not errs and family == "timing" and not c["window"]["stated"]:
            family, unchk = "uncheckable", "no_window"
        valid = int(not errs)
        n_ok += valid
        n_bad += 1 - valid
        conn.execute(
            "INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"{post['post_id']}-{run}-{i}", post["post_id"], run, model, P2_VERSION, post["author_username"],
             post["created_at"], family, c["lab"]["value"], c["model"]["value"],
             c["window"]["phrase"] if c["window"]["stated"] else "unstated",
             None if c["attribute"]["name"] == "none" else (c["attribute"]["name"] + (":" + c["attribute"]["detail"] if c["attribute"]["detail"] else "")),
             c["attribute"]["value"] or None, c["hedge"]["level"], c["origin"]["type"],
             c["origin"]["relayed_account"] or None, c["evidence"]["offered"], unchk,
             c["claim_span"]["text"], json.dumps(c, ensure_ascii=False), valid, "; ".join(errs) or None))
    checkable = conn.execute("SELECT COUNT(*) FROM claims WHERE post_id=? AND run=? AND valid=1 AND family!='uncheckable'",
                             (post["post_id"], run)).fetchone()[0]
    reason = None
    if checkable == 0:
        ur = out.get("uncheckable_reason", "other")
        if n_bad and not n_ok:
            reason = "extraction_rejected"
        elif n_ok:
            reason = "no_window"
        else:
            reason = ur if ur != "none" else "other"
    conn.execute("INSERT OR REPLACE INTO extractions VALUES (?,?,?,?,?,?,?,?,?)",
                 (post["post_id"], model, P2_VERSION, run, raw_id, _now(), n_ok, n_bad, reason))
    conn.commit()
    return n_ok


def eligible_posts(conn, author_ids: list[str] | None = None, start: str | None = None, end: str | None = None):
    q = "SELECT * FROM posts WHERE kind IN ('original','quote') AND source IN ('collection','daily')"
    args: list = []
    if author_ids:
        q += f" AND author_id IN ({','.join('?' * len(author_ids))})"
        args += author_ids
    if start:
        q += " AND created_at >= ?"
        args.append(start)
    if end:
        q += " AND created_at < ?"
        args.append(end)
    return conn.execute(q + " ORDER BY created_at", args).fetchall()


def run_all(conn, author_ids=None, start=None, end=None, log=print) -> dict:
    posts = eligible_posts(conn, author_ids, start, end)
    n_rel = n_claims = 0
    for i, p in enumerate(posts):
        about = run_pass1(conn, p)
        if about:
            n_rel += 1
            n_claims += run_pass2(conn, p)
        if i % 200 == 0:
            log(f"  extraction {i}/{len(posts)}")
    return {"posts": len(posts), "release_related": n_rel, "valid_claims": n_claims}
