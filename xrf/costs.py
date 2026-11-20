"""Cost meter. Every X read and every model call is checked here before it is made and recorded
after. A call is refused if its worst-case cost would take its budget past the cap."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from . import config

BUDGETS = ("x_reads", "discovery", "model_calls")


class CapExceeded(RuntimeError):
    pass


class PricingUnconfirmed(RuntimeError):
    pass


def caps() -> dict[str, float]:
    return {k: float(v) for k, v in config.load("caps")["caps_usd"].items()}


def pricing(provider: str) -> dict:
    p = config.load("pricing")[provider]
    if not p.get("confirmed"):
        raise PricingUnconfirmed(
            f"Prices for '{provider}' are not confirmed in config/pricing.yaml; refusing to call it.")
    return p


def spent(conn: sqlite3.Connection, budget: str | None = None) -> float | dict[str, float]:
    if budget:
        r = conn.execute("SELECT COALESCE(SUM(usd),0) FROM cost_events WHERE budget=?", (budget,)).fetchone()
        return float(r[0])
    return {b: spent(conn, b) for b in BUDGETS}


def check(conn: sqlite3.Connection, budget: str, worst_case_usd: float) -> None:
    if budget not in BUDGETS:
        raise ValueError(f"unknown budget {budget}")
    cap = caps()[budget]
    already = spent(conn, budget)
    if already + worst_case_usd > cap + 1e-9:
        raise CapExceeded(
            f"{budget}: spent {already:.4f} + worst case {worst_case_usd:.4f} > cap {cap:.2f} USD. Refusing.")


def record(conn: sqlite3.Connection, budget: str, provider: str, endpoint: str, units: float,
           unit: str, usd: float, worst_case_usd: float, raw_id: int | None = None,
           meta: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO cost_events(ts,budget,provider,endpoint,units,unit,usd,worst_case_usd,raw_id,meta_json)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), budget, provider, endpoint, units, unit, usd,
         worst_case_usd, raw_id, json.dumps(meta or {})))
    conn.commit()


def summary(conn: sqlite3.Connection) -> list[dict]:
    c = caps()
    s = spent(conn)
    return [{"budget": b, "spent_usd": round(s[b], 4), "cap_usd": c[b],
             "remaining_usd": round(c[b] - s[b], 4)} for b in BUDGETS]
