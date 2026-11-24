"""Command line: python -m xrf <command>. Run `python -m xrf -h` for the list."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, datetime, timezone

from . import config, costs, db, state


def _conn():
    return db.connect()


def cmd_costs(a):
    for s in costs.summary(_conn()):
        print(f"{s['budget']:12s} spent {s['spent_usd']:8.2f} / cap {s['cap_usd']:6.0f}  remaining {s['remaining_usd']:8.2f}")


def cmd_ledger_validate(a):
    from .ledger import load_releases, load_signals, validate_releases, validate_signals
    rel = load_releases()
    errs = validate_releases(rel) + validate_signals(load_signals(), rel)
    print(f"{len(rel)} releases, {len(load_signals())} signals, {len(errs)} problems")
    for e in errs:
        print("  " + e)
    sys.exit(1 if errs else 0)


def cmd_reresearch_sample(a):
    from . import reresearch
    print(f"{len(reresearch.sample())} rows in ledger/reresearch/sample.csv")


def cmd_reresearch_compare(a):
    from . import reresearch
    print(json.dumps(reresearch.compare(), indent=2))


def cmd_signals_x(a):
    from . import signals_x
    print(f"{signals_x.collect(_conn())} official X signals written to ledger/signals_x.csv")


def cmd_probe(a):
    from . import xapi
    print(xapi.probe(_conn()))


def _keys_report() -> dict:
    return {k: bool(config.env_key(k)) for k in ("X_BEARER_TOKEN", "XAI_API_KEY", "ANTHROPIC_API_KEY")}


def cmd_cohort(a):
    from . import cohort
    as_of = state.get_or_set_time("cohort_as_of")
    out = cohort.build(_conn(), as_of)
    state.set("pilot_accounts", out["pilot"])
    state.set("pilot_named", out.get("pilot_named") or [])
    state.set("cohort_size", out["cohort"])
    print(json.dumps(out, indent=2))


def _pilot() -> list[str]:
    p = state.get("pilot_accounts")
    if not p:
        path = config.COHORT / "pilot.csv"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                p = [r["username"] for r in csv.DictReader(f)]
    if not p:
        sys.exit("no pilot accounts: run `python -m xrf cohort` first")
    return p


def cmd_collect(a):
    from . import collect
    as_of = state.get_or_set_time("pilot_as_of")
    print(json.dumps(collect.collect(_conn(), _pilot(), as_of), indent=2))


def cmd_extract(a):
    from . import extract
    conn = _conn()
    ids = [r[0] for r in conn.execute(
        f"SELECT user_id FROM users WHERE lower(username) IN ({','.join('?' * len(_pilot()))})",
        [u.lower() for u in _pilot()])]
    print(json.dumps(extract.run_all(conn, ids), indent=2))


def _as_of() -> datetime:
    s = state.get("verdict_as_of")
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else datetime.now(timezone.utc)


def cmd_resolve(a):
    from . import resolve, rules
    tag = rules.assert_rules_tagged()
    if a.as_of:
        state.set("verdict_as_of", a.as_of)
    elif not state.get("verdict_as_of"):
        state.set("verdict_as_of", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    print(f"rules: {tag}")
    print(json.dumps(resolve.resolve_all(_conn(), as_of=_as_of()), indent=2))


def cmd_measures(a):
    from . import measures
    from .ledger import write_csv
    m = measures.compute(_conn(), accounts=_pilot())
    cols = sorted({k for r in m["accounts"] for k in r})
    write_csv(config.REPORT / "measures.csv", m["accounts"], ["account"] + [c for c in cols if c != "account"])
    print(f"wrote report/measures.csv ({len(m['accounts'])} accounts)")
    return m


def cmd_audit_sample(a):
    from . import audit
    print(f"{len(audit.make_sample(_conn()))} posts in audit/sample.csv")


def cmd_audit_alt(a):
    from . import audit
    conn = _conn()
    print(f"alt pass-2 on {audit.alt_run(conn)} posts")
    print(json.dumps(audit.agreement(conn), indent=2))


def cmd_audit_score(a):
    from . import audit
    s = audit.score(config.ROOT / a.path if not os.path.isabs(a.path) else a.path)
    (config.AUDIT / "scores.json").write_text(json.dumps(s, indent=2))
    print(json.dumps(s, indent=2))


def cmd_report(a):
    from . import measures, report
    conn = _conn()
    m = measures.compute(conn, accounts=state.get("pilot_accounts") or [])
    sc = config.AUDIT / "scores.json"
    md = report.build(conn, m, _as_of(), json.loads(sc.read_text()) if sc.exists() else None)
    (config.REPORT / "pilot.md").write_text(md, encoding="utf-8")
    print("wrote report/pilot.md")


def cmd_pilot(a):
    """Stages 2-8 in order. Stops at STOP 2 (after the report)."""
    keys = _keys_report()
    print("keys present:", keys)
    if not keys["X_BEARER_TOKEN"] or not keys["ANTHROPIC_API_KEY"]:
        sys.exit("X_BEARER_TOKEN and ANTHROPIC_API_KEY are both required for the pilot run.")
    if not (config.LEDGER / "signals_x.csv").exists():
        cmd_signals_x(a)
    if not state.get("pilot_accounts"):
        cmd_cohort(a)
    cmd_collect(a)
    cmd_extract(a)
    cmd_resolve(argparse.Namespace(as_of=None))
    cmd_measures(a)
    cmd_audit_sample(a)
    cmd_audit_alt(a)
    cmd_report(a)
    print("STOP 2: pilot report written. Do not run the full cohort or schedule the daily job until Alex has read it.")


def cmd_rebuild(a):
    """Regenerate every derived table and output from stored raw responses, offline (no spend)."""
    os.environ["XRF_OFFLINE"] = "1"
    conn = _conn()
    for t in db.DERIVED_TABLES:
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    from . import xparse
    n = xparse.reingest_all(conn)
    print(f"re-ingested {n} posts from raw")
    if (config.LEDGER / "signals_x.csv").exists():
        from . import signals_x
        signals_x.collect(conn, log=lambda *x: None)
    if state.get("cohort_as_of"):
        from . import cohort
        out = cohort.build(conn, state.get_or_set_time("cohort_as_of"), log=lambda *x: None)
        print(f"cohort rebuilt: {out['cohort']} accounts")
    if state.get("pilot_accounts") and conn.execute("SELECT COUNT(*) FROM posts WHERE source='collection'").fetchone()[0]:
        cmd_collect(a)
        cmd_extract(a)
        cmd_resolve(argparse.Namespace(as_of=None))
        cmd_measures(a)
        if (config.AUDIT / "sample.csv").exists():
            cmd_audit_sample(a)
            from . import audit
            audit.alt_run(conn)
    from . import daily
    daily.rederive_deletion_checks(conn)
    cmd_report(a)


def cmd_daily(a):
    from . import daily
    d = date.fromisoformat(a.date)
    users = a.accounts.split(",") if a.accounts else _pilot()
    print(json.dumps(daily.daily(_conn(), d, users, commit=not a.no_commit), indent=2))


def cmd_deletion_check(a):
    from . import daily
    print(json.dumps(daily.deletion_check(_conn(), date.fromisoformat(a.date)), indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(prog="xrf", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in [
        ("costs", cmd_costs, "spend against caps"),
        ("ledger-validate", cmd_ledger_validate, "check ledger rows and official sources"),
        ("reresearch-sample", cmd_reresearch_sample, "Stage 1: draw the 20%% re-research sample"),
        ("reresearch-compare", cmd_reresearch_compare, "Stage 1: disagreement rate vs the second pass"),
        ("signals-x", cmd_signals_x, "Stage 1b: official pre-release posts on X (needs X key)"),
        ("probe", cmd_probe, "one cheap X call to confirm field names"),
        ("cohort", cmd_cohort, "Stage 2: build cohort and pilot subset"),
        ("collect", cmd_collect, "Stage 3: collect pilot posts"),
        ("extract", cmd_extract, "Stage 4: blind extraction"),
        ("resolve", cmd_resolve, "Stage 5: resolve claims"),
        ("measures", cmd_measures, "Stage 6: per-account measures"),
        ("audit-sample", cmd_audit_sample, "Stage 7: write audit/sample.csv"),
        ("audit-alt", cmd_audit_alt, "Stage 7: pass 2 with the alternate model + agreement"),
        ("audit-score", cmd_audit_score, "Stage 7: precision/recall from a marked sample"),
        ("report", cmd_report, "Stage 8: write report/pilot.md"),
        ("pilot", cmd_pilot, "Stages 2-8 end to end (stops at STOP 2)"),
        ("rebuild", cmd_rebuild, "regenerate everything from stored raw data, offline"),
        ("daily", cmd_daily, "Stage 9: one day of prospective capture"),
        ("deletion-check", cmd_deletion_check, "Stage 9: 7- and 30-day deletion checks"),
    ]:
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        if name == "resolve":
            sp.add_argument("--as-of", help="verdict time, ISO (default: now / stored)")
        if name == "audit-score":
            sp.add_argument("path")
        if name == "daily":
            sp.add_argument("--date", required=True)
            sp.add_argument("--accounts", help="comma-separated; default: pilot accounts")
            sp.add_argument("--no-commit", action="store_true")
        if name == "deletion-check":
            sp.add_argument("--date", required=True)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
