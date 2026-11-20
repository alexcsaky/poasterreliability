"""Release ledger: loading, validation, and helpers used by resolution and baselines."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from . import config
from .rules import parse_dt

RELEASE_COLUMNS = ["release_id", "lab", "model", "tier", "modality", "aliases", "codenames", "announced_at",
                   "consumer_available_at", "api_available_at", "open_weights_at", "preview_at", "status",
                   "price", "context_window", "benchmarks", "source_urls", "notes"]
SIGNAL_COLUMNS = ["signal_id", "release_id", "lab", "model_ref", "signal_type", "posted_at", "author", "text",
                  "url", "notes"]
DATE_FIELDS = ["announced_at", "consumer_available_at", "api_available_at", "open_weights_at", "preview_at"]


def norm_name(s: str) -> str:
    return re.sub(r"[\s\-_.·:/()]+", "", (s or "").lower())


@dataclass
class Release:
    row: dict
    names: set[str] = field(default_factory=set)

    def __getitem__(self, k):
        return self.row.get(k, "")

    @property
    def id(self) -> str:
        return self.row["release_id"]

    def dt(self, f: str) -> datetime | None:
        return parse_dt(self.row.get(f) or None)

    @property
    def release_time(self) -> datetime | None:
        ts = [self.dt(f) for f in ("consumer_available_at", "api_available_at", "open_weights_at")]
        ts = [t for t in ts if t]
        return min(ts) if ts else None

    @property
    def preview_time(self) -> datetime | None:
        return self.dt("preview_at")

    @property
    def urls(self) -> list[str]:
        return [u.strip() for u in (self.row.get("source_urls") or "").split(";") if u.strip()]


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_releases(path: Path | None = None) -> list[Release]:
    out = []
    for r in read_csv(path or config.LEDGER / "releases.csv"):
        rel = Release(r)
        rel.names = {norm_name(r["model"])}
        for col in ("aliases", "codenames"):
            for a in (r.get(col) or "").split(";"):
                a = re.sub(r"\((confirmed|reported)\)", "", a).strip()
                if a:
                    rel.names.add(norm_name(a))
        out.append(rel)
    return out


def load_signals(path: Path | None = None) -> list[dict]:
    return read_csv(path or config.LEDGER / "signals.csv")


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


# ---- validation ---------------------------------------------------------------------------------

def is_official(url: str, lab_id: str) -> bool:
    lab = config.lab_by_id().get(lab_id)
    if not lab:
        return False
    u = url.strip()
    if "web.archive.org/web/" in u:
        u = re.sub(r"^https?://web\.archive\.org/web/[^/]+/", "", u)
    if not re.match(r"^https?://", u):
        u = "https://" + u
    p = urlparse(u)
    host = (p.hostname or "").lower().removeprefix("www.")
    path = p.path.lower()
    staff = (config.load("lab_staff").get("staff") or {}).get(lab_id) or []
    for dom in list(lab["official_domains"]) + [f"x.com/{h}" for h in staff]:
        dom = dom.lower().removeprefix("www.")
        if "/" in dom:                       # e.g. x.com/OpenAI, github.com/openai
            dh, dp = dom.split("/", 1)
            if host in (dh, "twitter.com" if dh == "x.com" else dh) and (path.strip("/") + "/").startswith(dp.lower() + "/"):
                return True
        elif host == dom or host.endswith("." + dom):
            return True
    return False


def validate_releases(rows: list[Release], period_start="2025-12-01", period_end=None) -> list[str]:
    errs = []
    seen = set()
    labs = config.lab_by_id()
    for r in rows:
        rid = r.id
        if rid in seen:
            errs.append(f"{rid}: duplicate release_id")
        seen.add(rid)
        if r["lab"] not in labs:
            errs.append(f"{rid}: unknown lab {r['lab']}")
        if r["tier"] not in ("flagship", "other"):
            errs.append(f"{rid}: tier must be flagship|other")
        if r["status"] not in ("released", "preview", "announced"):
            errs.append(f"{rid}: bad status {r['status']}")
        for f in DATE_FIELDS:
            try:
                r.dt(f)
            except ValueError:
                errs.append(f"{rid}: unparseable {f}={r[f]!r}")
        if not r.urls:
            errs.append(f"{rid}: no source_urls")
        elif not any(is_official(u, r["lab"]) for u in r.urls):
            errs.append(f"{rid}: no official source among {r.urls}")
        if r["status"] == "released" and not r.release_time:
            errs.append(f"{rid}: status=released but no availability date")
        a = r.dt("announced_at") or r.release_time or r.preview_time
        if a and a < parse_dt(period_start) - timedelta(days=1) and (not r.release_time or r.release_time < parse_dt(period_start)):
            errs.append(f"{rid}: outside period (before {period_start})")
    return errs


def validate_signals(rows: list[dict], releases: list[Release]) -> list[str]:
    ids = {r.id for r in releases}
    errs = []
    for s in rows:
        sid = s.get("signal_id")
        if s.get("release_id") and s["release_id"] not in ids:
            errs.append(f"{sid}: unknown release_id {s['release_id']}")
        if not s.get("url"):
            errs.append(f"{sid}: no url")
        elif not is_official(s["url"], s.get("lab", "")):
            errs.append(f"{sid}: url not on an official domain or account: {s['url']}")
        try:
            if not parse_dt(s.get("posted_at")):
                errs.append(f"{sid}: no posted_at")
        except ValueError:
            errs.append(f"{sid}: unparseable posted_at {s.get('posted_at')!r}")
    return errs


def first_signal_time(release: Release, signals: list[dict]) -> datetime | None:
    ts = [parse_dt(s["posted_at"]) for s in signals if s.get("release_id") == release.id and s.get("posted_at")]
    for f in ("announced_at", "preview_at"):
        if release.dt(f):
            ts.append(release.dt(f))
    if release.release_time:
        ts.append(release.release_time)
    return min(ts) if ts else None
