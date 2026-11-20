# Resolution rules (v1)

These rules decide whether a claim came true. They are fixed at the git tag `rules-v1`. After that tag,
this file changes only with a dated entry in `docs/DECISIONS.md`, and nothing downstream runs against
untagged rules (`xrf` checks that `RULES.md` matches the tagged version before Stage 5).

The rules are implemented in `xrf/rules.py` and `xrf/resolve.py`; where the code and this file
disagree, this file is right and the code is a bug.

## 1. Ground truth

1. Ground truth is `ledger/releases.csv` and `ledger/signals.csv`, built only from the labs' own
   sources (`docs/LEDGER_SCHEMA.md`). Nothing a cohort account posted is ever evidence.
2. Every verdict cites one ledger row and its official source URL, or states that no ledger row exists.
3. All times are UTC. A ledger date with no time is taken as 00:00–23:59 UTC of that day: a release on
   that day is inside any window that overlaps the day.

## 2. What "release" means

"Drops", "ships", "releases", "launches", "is out", "goes live" and similar mean the model is **usable**
on that date by at least one of:

- ordinary paying users of the lab's consumer product (any paid tier, including the top tier);
- ordinary developers through the lab's public API (a public paid preview counts; a whitelist does not);
- anyone, as downloadable open weights.

The **release time** of a ledger row is the earliest of `consumer_available_at`, `api_available_at`
and `open_weights_at`.

A limited preview for selected testers (`preview_at`, or `status=preview`) is **partial**: a timing
claim whose window contains only a tester preview, and no release, resolves `partial`.
An announcement with no availability (`status=announced`) is not a release.

## 3. Timing claims: windows

A timing claim says a named model (or named model family) will be released within a window. The
window starts at the post's timestamp and ends at the deadline below. "Week" is the ISO week, Monday
00:00 to Sunday 23:59:59 UTC. "Month" is the calendar month in UTC.

| Phrase in the post | Deadline (window end) | Notes |
|---|---|---|
| "today", "tonight", "later today", "this morning/afternoon/evening", "in a few hours", "in N hours" | post time + 24 h | |
| "tomorrow" | post time + 48 h | |
| "this week", "later this week", "end of the week", "by the weekend", "within the week" | end of the post's ISO week | posted on a weekend: still that Sunday |
| "this weekend", "over the weekend" | end of the post's ISO week | |
| "next week" | end of the following ISO week | released before the following week starts: `partial` (early) |
| "in N days" / "in N weeks" | post time + N days (+1 day grace) / N weeks (+1 day grace) | |
| "this month", "later this month", "end of the month", "within the month" | end of the post's calendar month | |
| "next month" | end of the following calendar month | released before that month starts: `partial` (early) |
| "imminent", "any day now", "very soon", "super soon", "any minute", "any moment", "any hour now", "momentarily" | post time + 7 days | |
| "soon", "soonish", "coming", "shortly", "around the corner", "on the way", "incoming" | tested at 7, 14 **and** 30 days | headline uses 14 days; the 7- and 30-day results are reported as sensitivity |
| "in the coming weeks", "next few weeks", "in a few weeks", "within weeks" | post time + 30 days | |
| "by end of year", "before the year ends", "EOY", "this year", "before <next year>" | 31 Dec of the post's year, 23:59:59 | |
| "Q1"…"Q4", "H1", "H2" (+ optional year) | end of that quarter or half | |
| a named weekday ("Thursday", "next Thursday") | that day: the next one on or after the post date | released within ±12 h of that UTC day: `correct`; otherwise `incorrect` |
| an explicit date ("Dec 3", "3 December", "12/3" read as month/day) | that day (a date more than 60 days before the post means next year) | same ±12 h tolerance |
| "before <event>" (e.g. "before Gemini 4") | the release time of that event's ledger row | if the event has no ledger row, `uncheckable` |
| no time phrase at all | **unstated** | the claim is a timing claim only if it has a window; with none it is stored as `uncheckable` (reason: no window) |

Phrases not in this table are mapped by the closest row only if the mapping is unambiguous and listed
in `xrf/rules.py` (`PHRASES`); otherwise the claim is `uncheckable` (reason: window not mappable) and
the phrase is logged in the resolution log for a rules update.

## 4. Timing verdicts

Let *R* be the release time of the claimed model: the earliest release of any ledger row the claim's
model name matches (section 6) that falls **after the post**.

| Situation | Verdict |
|---|---|
| *R* is inside the window | `correct` |
| *R* is before the window's lower bound for "next week"/"next month" | `partial` (early) |
| no release inside the window, but a tester preview inside it | `partial` |
| window not yet closed and no release yet | `open` |
| window closed, no release inside it, and the model shipped later | `incorrect` |
| window closed and the model never shipped | `open` until window end + 14 days, then `incorrect` |
| model was already released before the post | `uncheckable` (reason: already out) — the claim is not a forecast |
| the post names no model or model family | `uncheckable` (reason: no model named) |

A claim about a model family ("a new Gemini model", "new Claude") matches any ledger row in that family
from the named lab.

## 5. Attribute claims

An attribute claim states a property of a model: its name, price, context window, a benchmark figure,
its modality, or its release route (API, app, open weights). It resolves against the first ledger row the
model name matches, once that row is released.

| Attribute | Correct if | Partial if |
|---|---|---|
| name ("it will be called X") | the lab releases a model whose official name or alias is X, by the claim's window (or within 180 days of the post if no window) | the name matches apart from a suffix ("Pro", "mini", version digit) |
| price (per Mtok input/output, or consumer plan) | equal to the ledger value | within 10% |
| context window | equal to the ledger value (128k = 128,000 or 131,072) | within 10% |
| benchmark figure | within 0.5 percentage points (or 0.5% relative for non-percent scores) of the lab's stated figure for the same benchmark | within 2 points |
| modality / route | ledger agrees | — |
| anything else | `uncheckable` (reason: attribute not in ledger) | |

If the ledger row has no value for the attribute, the claim is `uncheckable` (reason: not stated by lab).
If the model has not been released, the claim is `open`; if it never ships within 180 days of the post
(or by its window + 14 days if it states one), it is `uncheckable` (reason: model never shipped).

## 6. Matching names to the ledger

1. Exact, case-insensitive match on `model`, `aliases` or `codenames` (after removing spaces, hyphens
   and dots) is done in code.
2. Codenames and loose names ("the new Gemini", "o5", "Strawberry 2") are matched by a language model
   that sees only the claim's lab and model string and the ledger's names, aliases and codenames. It
   never sees the post, the account, or any dates. Every match is stored with its reason in
   `alias_matches`; no match means no ledger row.
3. Codenames marked `(reported)` in the ledger may be used for matching, never as evidence of a release.

## 7. Tier

`flagship` is the lab's top general-purpose line listed under `flagship_lines` in `config/labs.yaml`
(e.g. GPT-5.x, Claude Opus, Gemini Pro/Deep Think, Grok numbered releases). Everything else is `other`.
The claimed tier of a timing claim is the tier of the matched ledger row; for a family claim with no
single row, the tier implied by the family name (flagship family → `flagship`, otherwise `any`).

## 8. Hedges, relays, jokes

- Hedge levels (`flat`, `hedged`, `question`, `joke`) are recorded, not used to change verdicts.
  Accuracy is reported for flat and hedged claims separately. Questions and jokes are excluded from
  accuracy and counted in the vagueness rate.
- A relay ("hearing from X that…", "per @Y") is scored to the posting account like any other claim and
  marked as a relay for the originality measure.

## 9. Observation end

Verdicts are computed as of the `as_of` time recorded in the report (default: the run time). A
backtest misses posts deleted before collection, so backtest accuracy figures are upper bounds.
