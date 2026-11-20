"""Idempotent, metered calls with unmodified raw storage.

Every external call is keyed by (provider, endpoint, params). If a successful response for that key
is already stored, it is returned from disk at no cost: this is what makes every stage resumable and
lets `xrf rebuild` regenerate all figures without spending anything. With XRF_OFFLINE=1 a cache miss
is an error instead of a network call."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from . import config, costs


class OfflineMiss(RuntimeError):
    pass


@dataclass
class Raw:
    id: int
    status: int
    body: bytes
    requested_at: str
    cached: bool

    def json(self):
        return json.loads(self.body)


def request_key(provider: str, endpoint: str, params: dict) -> str:
    blob = json.dumps({"p": provider, "e": endpoint, "q": params}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def load_body(rel_path: str) -> bytes:
    with gzip.open(config.DATA / rel_path, "rb") as f:
        return f.read()


def lookup(conn: sqlite3.Connection, key: str) -> Raw | None:
    r = conn.execute("SELECT id,status,body_path,requested_at FROM raw_responses WHERE request_key=? "
                     "AND status BETWEEN 200 AND 299 ORDER BY id DESC LIMIT 1", (key,)).fetchone()
    if not r:
        return None
    return Raw(r["id"], r["status"], load_body(r["body_path"]), r["requested_at"], True)


def store(conn: sqlite3.Connection, key: str, provider: str, endpoint: str, params: dict,
          status: int, body: bytes, usd: float = 0.0) -> Raw:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sha = hashlib.sha256(body).hexdigest()
    rel = f"raw/{provider}/{now[:10]}/{key[:16]}-{sha[:12]}.json.gz"
    path = config.DATA / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as f:
            f.write(body)
    cur = conn.execute(
        "INSERT INTO raw_responses(request_key,provider,endpoint,params_json,status,requested_at,body_path,"
        "body_sha256,usd) VALUES (?,?,?,?,?,?,?,?,?)",
        (key, provider, endpoint, json.dumps(params, sort_keys=True, ensure_ascii=False), status, now, rel, sha, usd))
    conn.commit()
    return Raw(cur.lastrowid, status, body, now, False)


def call(conn: sqlite3.Connection, *, provider: str, endpoint: str, params: dict, budget: str,
         worst_case_usd: float, do_request: Callable[[], tuple[int, bytes]],
         cost_of: Callable[[int, bytes], tuple[float, float, str]]) -> Raw:
    """do_request() -> (status, body). cost_of(status, body) -> (usd, units, unit)."""
    key = request_key(provider, endpoint, params)
    hit = lookup(conn, key)
    if hit:
        return hit
    if os.environ.get("XRF_OFFLINE") == "1":
        raise OfflineMiss(f"offline: no stored response for {provider} {endpoint} {params}")
    costs.check(conn, budget, worst_case_usd)
    status, body = do_request()
    usd, units, unit = cost_of(status, body) if 200 <= status < 300 else (0.0, 0.0, "error")
    raw = store(conn, key, provider, endpoint, params, status, body, usd)
    costs.record(conn, budget, provider, endpoint, units, unit, usd, worst_case_usd, raw.id,
                 {"status": status})
    return raw
