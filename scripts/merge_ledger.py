"""Merge the per-lab research CSVs into ledger/releases.csv and ledger/signals.csv.
Usage: python scripts/merge_ledger.py <dir with *_releases.csv and *_signals.csv>
Normalises whitespace and column order, sorts rows, and reports validation problems. Does not invent values."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from xrf import config  # noqa: E402
from xrf.ledger import (RELEASE_COLUMNS, SIGNAL_COLUMNS, load_releases, load_signals, read_csv,  # noqa: E402
                        validate_releases, validate_signals, write_csv)

src = Path(sys.argv[1])
rels, sigs = [], []
for f in sorted(src.glob("*_releases.csv")):
    rels += read_csv(f)
for f in sorted(src.glob("*_signals.csv")):
    sigs += read_csv(f)
import yaml  # noqa: E402
fixes = yaml.safe_load((config.LEDGER / "merge_fixes.yaml").read_text()) or {}
drop_r, drop_s = fixes.get("drop_releases") or {}, fixes.get("drop_signals") or {}
rels = [r for r in rels if r.get("release_id") not in drop_r]
sigs = [s for s in sigs if s.get("signal_id") not in drop_s and s.get("release_id") not in drop_r]
for rid, kv in (fixes.get("set_fields") or {}).items():
    for r in rels:
        if r["release_id"] == rid:
            r.update(kv)
# Fill blanks from the independent second pass (after the disagreement rate has been measured; D-020).
second = {r["release_id"]: r for r in read_csv(config.LEDGER / "reresearch" / "second_pass.csv")}
for r in rels:
    s2 = second.get(r["release_id"])
    if not s2:
        continue
    fill = ["price", "context_window", "benchmarks"]
    if (s2.get("status") or "").strip() == (r.get("status") or "").strip():
        fill += ["consumer_available_at", "api_available_at", "open_weights_at"]
    filled = [f for f in fill if not (r.get(f) or "").strip() and (s2.get(f) or "").strip()]
    for f in filled:
        r[f] = s2[f]
    if filled:
        extra = [u for u in (s2.get("source_urls") or "").split(";") if u.strip() and u.strip() not in r["source_urls"]]
        r["source_urls"] = ";".join([r["source_urls"]] + [u.strip() for u in extra])
        r["notes"] = (r.get("notes") or "") + f" [{', '.join(filled)} filled from independent re-research (D-020)]"
clean = lambda r, cols: {c: " ".join((r.get(c) or "").split()) for c in cols}
rels = sorted((clean(r, RELEASE_COLUMNS) for r in rels), key=lambda r: (r["lab"], r["announced_at"] or r["api_available_at"] or r["consumer_available_at"], r["release_id"]))
sigs = sorted((clean(s, SIGNAL_COLUMNS) for s in sigs), key=lambda s: (s["lab"], s["posted_at"], s["signal_id"]))
write_csv(config.LEDGER / "releases.csv", rels, RELEASE_COLUMNS)
write_csv(config.LEDGER / "signals.csv", sigs, SIGNAL_COLUMNS)
R = load_releases()
errs = validate_releases(R) + validate_signals(load_signals(), R)
print(f"{len(rels)} releases, {len(sigs)} signals, {len(errs)} problems")
for e in errs:
    print("  " + e)
