from datetime import datetime, timezone

import pytest

from xrf import costs, db, measures, rules
from xrf.ledger import is_official, load_releases, validate_releases

T = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)   # a Thursday


def W(p, t=T):
    return rules.window_for(p, t)


def test_windows():
    assert W("unstated") == "unstated"
    assert W("today").days == pytest.approx(1)
    assert W("this week").end == datetime(2026, 10, 4, 23, 59, 59, tzinfo=timezone.utc)
    nw = W("next week")
    assert nw.lower == datetime(2026, 10, 5, tzinfo=timezone.utc) and nw.end.day == 11
    assert W("this month").end.day == 31
    nm = W("next month")
    assert nm.end == datetime(2026, 11, 30, 23, 59, 59, tzinfo=timezone.utc)
    s = W("soon")
    assert set(s.variants) == {"soon7", "soon14", "soon30"} and s.days == pytest.approx(14)
    assert W("imminent").days == pytest.approx(7)
    assert W("by end of year").end.month == 12
    assert W("in 2 weeks").days == pytest.approx(15)
    d = W("Oct 9")
    assert d.point == datetime(2026, 10, 9, tzinfo=timezone.utc)
    assert W("Q4").end.month == 12
    assert W("whenever the vibes are right") is None


def test_official_sources():
    assert is_official("https://openai.com/index/x", "openai")
    assert is_official("https://help.openai.com/en/articles/1", "openai")
    assert is_official("https://x.com/OpenAI/status/123", "openai")
    assert not is_official("https://x.com/someleaker/status/1", "openai")
    assert not is_official("https://www.theverge.com/x", "openai")
    assert is_official("https://web.archive.org/web/2026/https://openai.com/index/x", "openai")
    assert is_official("https://huggingface.co/Qwen/Qwen3", "alibaba")


def test_fixture_ledger_valid():
    assert validate_releases(load_releases()) == []


def test_cost_cap_refuses(tmp_path):
    conn = db.connect(tmp_path / "c.sqlite")
    costs.check(conn, "model_calls", 74.0)
    costs.record(conn, "model_calls", "anthropic", "messages", 1, "tokens", 74.5, 74.5)
    with pytest.raises(costs.CapExceeded):
        costs.check(conn, "model_calls", 1.0)
    costs.check(conn, "x_reads", 149.0)


def test_wilson_and_shrinkage():
    lo, hi = measures.wilson(8, 10)
    assert 0.44 < lo < 0.5 and 0.94 < hi < 0.97
    fit = measures.fit_beta_binomial([5, 7, 2, 9], [10, 10, 10, 10])
    assert fit and all(x > 0 for x in fit)


def test_baseline():
    b = measures.Baseline()
    p = b.p("openai", "flagship", 7, datetime(2026, 11, 1, tzinfo=timezone.utc))
    # one OpenAI flagship release (10 Oct) in ~11 months of daily 7-day windows
    assert 0 < p < 0.05
    assert b.p(None, "any", 30, datetime(2026, 11, 1, tzinfo=timezone.utc)) > p


def test_search_terms_order_is_stable_across_processes():
    """Equal-length aliases used to come out in hash order, so re-runs built different queries (cache misses,
    paid twice). The order must not depend on PYTHONHASHSEED."""
    import os
    import subprocess
    import sys
    code = ("from xrf import xapi; print(xapi.ordered_terms({'gpt-x-mini','GPT-X-Mini','gpt-x-nano','GPT-X','b','a'}))")
    outs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                           env={**os.environ, "PYTHONHASHSEED": str(seed)}).stdout for seed in range(6)}
    assert len(outs) == 1
    assert outs.pop().strip() == "['a', 'b', 'GPT-X', 'GPT-X-Mini', 'gpt-x-mini', 'gpt-x-nano']"
