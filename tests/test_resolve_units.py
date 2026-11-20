from datetime import datetime, timezone

from xrf.ledger import Release
from xrf.resolve import attribute_verdict, timing_verdict
from xrf.rules import window_for


def R(rid, rel=None, prev=None, **kw):
    row = {"release_id": rid, "lab": "openai", "model": rid, "tier": "flagship", "consumer_available_at": rel or "",
           "api_available_at": "", "open_weights_at": "", "preview_at": prev or "", "announced_at": rel or "",
           "source_urls": "https://openai.com/x", "price": "", "context_window": "", "benchmarks": "", "modality": "multimodal"}
    row.update(kw)
    return Release(row, {rid})


def t(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


POST = t("2026-10-01T10:00:00")   # Thursday
AS_OF = t("2026-11-30T00:00:00")


def V(phrase, rels, as_of=AS_OF, fam=False):
    w = window_for(phrase, POST)
    return timing_verdict(POST, w, w.end, rels, as_of, is_family=fam)[0]


def test_timing_cases():
    assert V("this week", [R("a", "2026-10-03")]) == "correct"
    assert V("this week", [R("a", "2026-10-06")]) == "incorrect"
    assert V("next week", [R("a", "2026-10-02")]) == "partial"           # early
    assert V("next week", [R("a", "2026-10-07")]) == "correct"
    assert V("this week", [R("a", "", prev="2026-10-02")]) == "partial"   # tester preview only
    assert V("this week", [], as_of=t("2026-10-10T00:00:00")) == "open"   # never-shipped grace
    assert V("this week", [], as_of=t("2026-10-30T00:00:00")) == "incorrect"
    assert V("this week", [R("a", "2026-09-01")]) == "uncheckable"         # already out
    assert V("this week", [R("a", "2026-09-01"), R("b", "2026-10-02")], fam=True) == "correct"
    assert V("this week", [R("a", "2026-09-01")], fam=True, as_of=t("2026-10-30T00:00:00")) == "incorrect"
    assert V("Oct 3", [R("a", "2026-10-03")]) == "correct"
    assert V("Oct 3", [R("a", "2026-10-05")]) == "incorrect"
    assert V("this week", [R("a", "2026-12-01")], as_of=t("2026-10-02T00:00:00")) == "open"


def test_attributes():
    r = R("a", "2026-10-03", price="input $2/Mtok; output $12/Mtok", context_window="1000000",
          benchmarks="SWE-bench Verified=81.2%; GPQA Diamond=90.1%")
    assert attribute_verdict("context_window", "1M", r)[0] == "correct"
    assert attribute_verdict("context_window", "1.05M", r)[0] == "partial"
    assert attribute_verdict("context_window", "2M", r)[0] == "incorrect"
    assert attribute_verdict("price:output price", "$12", r)[0] == "correct"
    assert attribute_verdict("price:input price", "$3", r)[0] == "incorrect"
    assert attribute_verdict("benchmark:SWE-bench Verified", "81%", r)[0] == "correct"
    assert attribute_verdict("benchmark:SWE-bench Verified", "79.5%", r)[0] == "partial"
    assert attribute_verdict("benchmark:ARC-AGI-2", "50%", r)[0] == "uncheckable"
