# Pilot report: X release-forecaster tracker

Generated 2026-11-20 05:03 UTC (regenerate with `python -m xrf rebuild`); verdicts as of 2026-11-20 05:03 UTC. Every figure below is regenerated from stored raw API responses, the ledger and `RULES.md` (tag `rules-v1`). Nothing here is published; the repo is private.

> **Backtest caveat.** A backtest only sees posts that still existed when collected. Posts deleted before collection (plausibly the wrong ones) are missing, so **every accuracy figure in this report is an upper bound**.

> **No pilot data yet.** No posts have been collected, so the yield, measures and audit sections are empty. See `docs/STATUS.md` for what is blocking collection.

## Ground truth

`ledger/releases.csv`: 259 release events (1 Dec 2025 to 20 Nov 2026); `ledger/signals.csv`: 98 official pre-release signals.

| lab | releases | flagship |
|---|---|---|
| alibaba | 53 | 7 |
| anthropic | 16 | 12 |
| deepseek | 11 | 5 |
| google_deepmind | 54 | 6 |
| meta | 14 | 7 |
| mistral | 19 | 3 |
| moonshot | 5 | 4 |
| openai | 49 | 9 |
| xai | 20 | 8 |
| zhipu | 18 | 5 |

Independent re-research of a random 20% of rows (52 rows, 308 fields compared): field-level disagreement rate **14.0%**, of which real conflicts (not a missing value or a one-day date difference) 2.6%; rows with any disagreement 51.9%, with a real conflict 15.4%. Details: `ledger/reresearch/report.md`.

## Yield

| account | posts | release-related | checkable claims | resolved | open |
|---|---|---|---|---|---|
| **total** | 0 | 0 | 0 | 0 | 0 |

## Measures

Headline: timing accuracy on claims made **before any official signal** for the model (signals = `ledger/signals.csv` plus the lab's own announcement and preview dates). Flat and hedged claims only; questions and jokes are excluded. Partial verdicts count as not correct. Intervals are 95% Wilson. Accounts with fewer than 20 resolved claims are listed but not ranked. Shrunk estimates use a beta-binomial fitted on the cohort (fit: None).

| rank | account | pre-signal timing acc | skill vs base (pre) | all timing acc | skill vs base | attribute acc | shrunk acc | median lead (h) | original share | vagueness |
|---|---|---|---|---|---|---|---|---|---|---|

Flat vs hedged timing claims, and the 'soon' sensitivity (7/14/30 days; 14 is used above):

| account | flat | hedged | soon@7 | soon@14 | soon@30 |
|---|---|---|---|---|---|

## Audit

Second-model agreement: not yet run (no sample).

Human marking of `audit/sample.csv`: not done yet (precision/recall come from `python -m xrf audit-score`).

## Costs against caps

| budget | spent (USD) | cap (USD) | remaining |
|---|---|---|---|
| x_reads | 0.00 | 150 | 150.00 |
| discovery | 0.00 | 75 | 75.00 |
| model_calls | 0.00 | 75 | 75.00 |

X spend is recorded on the worst-case assumption that objects returned through expansions are billed (the docs do not say); reconcile against the X developer console.

### Estimate for the full cohort

Basis: ASSUMED 8 original+quote posts per account per day (no pilot data yet); quoted share 30%; release-related share 35%; pass 1 ≈ $0.00016/post, pass 2 ≈ $0.026/release-related post.

| scope | posts | X reads (USD) | model calls (USD) | total (USD) |
|---|---|---|---|---|
| 100 accounts x 90 days | 72,000 | 360–471 | 667 | 1,027–1,138 |
| 100 accounts x 12 months | 292,000 | 1,460–1,910 | 2,705 | 4,165–4,615 |

Excludes cohort discovery (already paid once) and the daily job's deletion checks (about $0.005 per claim-bearing post per check). X caps post reads at 3M a month.

## What broke

- **No API keys in the build environment.** `X_BEARER_TOKEN`, `XAI_API_KEY` and `ANTHROPIC_API_KEY` were all unset,
  so Stages 2–8 have been built and tested only against a fake X/LLM world (`tests/`). No cohort, posts, claims or
  verdicts exist yet, and no money has been spent.
- **Several lab sites block automated reading.** openai.com and help.openai.com returned 403 to every fetch, x.com
  returned 402, and web.archive.org was unreachable. The OpenAI rows therefore rest on developers.openai.com
  (API changelog, model and pricing pages), system cards and official Hugging Face pages; plan-level ChatGPT rollout
  dates and many headline benchmarks are blank (each gap is explained in the row's notes).
- **Official signals are web-only.** Teasers posted only on X by official accounts or staff are under-recorded until
  they can be pulled through the X API (D-008). This flatters the "before any official signal" headline.
- **X documentation is inconsistent on field names** (`tweet.fields` vs `post.fields`); one probe call settles it
  before the pilot (D-002).

Automatic counts: 0 extracted claims rejected by the span validator; 0 timing claims with a window phrase the rules could not map.

