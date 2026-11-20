"""End to end on the fake world: cohort -> collection -> blind extraction -> resolution -> measures ->
audit -> report, then an offline rebuild that must reproduce the same report without any calls."""
import json
import os
from datetime import date, datetime, timezone

import pytest

import fakeworld as fw
from xrf import (audit, cohort, collect, config, costs, db, daily, extract, llm, measures, report, resolve,
                 state, xapi, xparse)

AS_OF = datetime(2026, 11, 15, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    xapi._send = fw.x_send
    llm._send = fw.llm_send
    c = db.connect()
    yield c


def test_cohort(conn):
    out = cohort.build(conn, AS_OF, log=lambda *a: None)
    names = {r["username"] for r in measures_csv(config.COHORT / "cohort.csv")}
    assert names == {"alice", "bob", "carol"}
    ex = {r["username"]: r["reason"] for r in measures_csv(config.COHORT / "excluded.csv")}
    assert "eve" in ex and "staff" in ex["eve"]
    assert "followers" in ex["dave"]
    ranked = measures_csv(config.COHORT / "cohort.csv")
    assert ranked[0]["username"] == "alice"           # highest median impressions
    assert sorted(out["pilot"]) == ["alice", "bob", "carol"]
    state.set("pilot_accounts", out["pilot"])


def measures_csv(p):
    import csv
    with open(p) as f:
        return list(csv.DictReader(f))


def test_collect_excludes_replies(conn):
    collect.collect(conn, ["alice", "bob", "carol"], AS_OF, log=lambda *a: None)
    kinds = dict(conn.execute("SELECT post_id, kind FROM posts WHERE source='collection'").fetchall())
    assert "104" not in kinds and kinds["301"] == "quote"
    q = conn.execute("SELECT quoted_text, quoted_author_username FROM posts WHERE post_id='301'").fetchone()
    assert q[0] == "Gemini 9 this week" and q[1] == "alice"
    assert conn.execute("SELECT captured_at FROM posts WHERE post_id='101'").fetchone()[0]


def test_extract_blind_and_validated(conn):
    ids = ["1", "2", "3"]
    out = extract.run_all(conn, ids, log=lambda *a: None)
    assert out["posts"] == 9 and out["release_related"] == 8
    hype = conn.execute("SELECT uncheckable_reason FROM extractions WHERE post_id='202'").fetchone()[0]
    assert hype == "pure_hype"
    # the extractor input never contains ledger information
    raw = conn.execute("SELECT params_json FROM raw_responses WHERE provider='anthropic'").fetchall()
    for (p,) in raw:
        d = json.loads(p)
        if "claims" in json.dumps(d["schema"]):
            assert "release" not in d["content"][0]["text"].lower() or "releases:" not in d["content"][0]["text"].lower()
            assert "openai.com" not in d["content"][0]["text"]


def test_validator_rejects_unsupported_span(conn):
    post = {"text": "GPT-9 soon", "quoted_text": None, "media_json": "[]", "quoted_media_json": None,
            "quoted_author_username": None}
    c = fw.CANNED["GPT-9 soon"]["claims"][0]
    errs = extract.validate_claim(c, post)
    assert any(e.startswith("window") for e in errs)


def test_resolve(conn):
    counts = resolve.resolve_all(conn, as_of=AS_OF)
    v = {r[0].split("-")[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT claim_id, verdict, signal_before_post FROM verdicts WHERE variant='main'")}
    assert v["101"] == ("correct", 0)          # GPT-9 next week -> released 10 Oct, before the 5 Oct teaser? no: post 1 Oct precedes signal
    assert v["102"][0] == "incorrect"           # Gemini 9 this week -> released 20 Oct
    assert v["201"][0] == "incorrect"           # 2M context vs 1,000,000
    assert v["301"][0] == "correct"             # soon (14d) -> 20 Oct
    assert v["303"][0] == "open"                # GPT-10 today, posted 13 Nov: grace running
    m = conn.execute("SELECT method FROM alias_matches").fetchall()
    assert m, "loose names go through the matcher and are stored with a reason"


def test_measures_and_report(conn):
    state.set("verdict_as_of", AS_OF.strftime("%Y-%m-%dT%H:%M:%SZ"))
    m = measures.compute(conn, accounts=["alice", "bob", "carol"])
    a = {r["account"]: r for r in m["accounts"]}
    assert a["alice"]["timing_n"] == 2 and a["alice"]["timing_correct"] == 1
    assert a["alice"]["pre_n"] == 2
    assert a["bob"]["vagueness_rate"] == pytest.approx(2 / 3)
    assert a["carol"]["relay_share"] == pytest.approx(0.5)
    assert a["alice"]["timing_skill"] is not None
    audit.make_sample(conn, n=200)
    audit.alt_run(conn)
    ag = audit.agreement(conn)
    assert ag["claim_f1"] == pytest.approx(1.0)
    md = report.build(conn, m, AS_OF)
    assert "upper bound" in md and "@alice" in md
    (config.REPORT / "pilot.md").write_text(md)


def test_rebuild_offline_reproduces(conn):
    from xrf import cli
    state.set("cohort_as_of", AS_OF.strftime("%Y-%m-%dT%H:%M:%SZ"))
    state.set("pilot_as_of", AS_OF.strftime("%Y-%m-%dT%H:%M:%SZ"))
    before = (config.REPORT / "pilot.md").read_text().split("\n", 3)[3]
    spent = costs.spent(conn)
    n_calls = dict(fw.calls)
    cli.main(["rebuild"])
    after = (config.REPORT / "pilot.md").read_text().split("\n", 3)[3]
    os.environ.pop("XRF_OFFLINE", None)
    assert fw.calls == n_calls, "rebuild must not call any API"
    assert costs.spent(conn) == spent
    assert before == after


def test_daily_and_deletion(conn):
    r1 = daily.daily(conn, date(2026, 11, 12), ["carol"], commit=True, log=lambda *a: None)
    r2 = daily.daily(conn, date(2026, 11, 13), ["carol"], commit=True, log=lambda *a: None)
    assert r1["claims_logged"] == 1 and r2["claims_logged"] == 1 and r1["committed"] and r2["committed"]
    hashes = (config.PROSPECTIVE / "HASHES.txt").read_text().splitlines()
    assert len(hashes) == 2
    from datetime import timedelta
    out = daily.deletion_check(conn, date.today() + timedelta(days=31))
    assert out['day7']['checked'] > 0 and out['day30']['checked'] > 0
    gone = conn.execute("SELECT post_id FROM deletion_checks WHERE exists_now=0").fetchall()
    assert ("201",) in [tuple(g) for g in gone]


def test_signals_x(conn):
    from xrf import signals_x
    from xrf.ledger import load_signals
    n = signals_x.collect(conn, log=lambda *a: None)
    assert n == 1                                   # the @OpenAI teaser; @eve is not a listed account
    sig = [s for s in load_signals() if s["signal_id"].startswith("openai-gpt-9-x")]
    assert all(s["url"].startswith("https://x.com/") for s in sig)


def test_cap_enforced_end_to_end(conn):
    costs.record(conn, "x_reads", "x", "test", 0, "x", costs.caps()["x_reads"], 0)
    with pytest.raises(costs.CapExceeded):
        collect.collect_account(conn, "alice", datetime(2026, 9, 1, tzinfo=timezone.utc),
                                datetime(2026, 9, 2, tzinfo=timezone.utc))
