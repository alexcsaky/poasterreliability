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
