# AGENTS.md: shared brief

This repo is a standalone research pipeline that builds a checkable record of which X accounts
forecast AI model releases correctly. Version 1 covers release claims only: timing (when a model
ships) and attributes (name, price, specs, benchmark figures). Read this file before working here.

## Fixed decisions (do not change; ask Alex if one blocks you)

- Ground truth comes first and comes only from the labs' own sources (`ledger/`, `docs/LEDGER_SCHEMA.md`).
- The cohort is the top 100 influencer-type accounts that post about model releases, ranked by reach.
  Official lab accounts and lab staff are not in the cohort; their posts are official signals.
- Claim extraction never sees outcomes (no ledger, no search, no later posts).
- Collection is exhaustive per account: every original and quote post in the window.
- Accounts will be named and code, method and data will be open source, but the repo stays private and
  nothing is published until Alex says so.
- Official X API only. No scrapers, no unofficial endpoints. Never write to X.
- Standalone: plain Python, SQLite, flat files. No web service.

## Guardrails

- Keys from environment only: `X_BEARER_TOKEN`, `XAI_API_KEY` (optional, discovery only), `ANTHROPIC_API_KEY`.
  Never commit keys.
- Every X read and model call goes through the cost meter (`xrf/costs.py` via `xrf/rawstore.py`). Caps in
  `config/caps.yaml`: 150 USD X reads, 75 USD discovery, 75 USD model calls. The meter refuses any call
  whose worst case would pass a cap. Do not bypass it.
- Every stage is idempotent and resumable: each external request is cached by its parameters and its
  raw response stored unmodified (gzip) under `data/raw/`. Fixed run times live in `config/run_state.json`
  so re-runs make identical requests. Do not edit that file by hand.
- `RULES.md` is frozen at git tag `rules-v1`. Change it only with a dated entry in `docs/DECISIONS.md`
  that records the new file's `RULES.md sha256 <first 12 hex>`; resolution refuses to run otherwise.
- STOP points: after Stage 2 (cohort for Alex to look over; continue with the pilot subset only) and after
  Stage 8 (pilot report; do not run the full cohort or schedule the daily job until Alex has read it).

## Layout

| path | what |
|---|---|
| `xrf/` | the pipeline (`python -m xrf -h`) |
| `config/` | labs, caps, prices, models, lab staff, run state |
| `ledger/` | `releases.csv`, `signals.csv`, re-research check |
| `RULES.md` | resolution rules (tagged) |
| `cohort/` | `cohort.csv`, `excluded.csv`, `pilot.csv` |
| `audit/` | sample for human marking, scores |
| `report/` | `pilot.md`, `measures.csv`, `what_broke.md` |
| `prospective/` | daily claim files and their hashes (Stage 9) |
| `data/` | `raw/` responses (kept) and `xrf.sqlite` (derived; rebuildable) |
| `docs/` | `STATUS.md`, `DECISIONS.md`, `LEDGER_SCHEMA.md`, `api_docs_findings.md` |

## Commands

```bash
pip install -r requirements.txt
python -m pytest -q                 # offline tests on a fake X/LLM world
python -m xrf ledger-validate       # every ledger row has an official source
python -m xrf pilot                 # Stages 2-8, stops at STOP 2 (needs X + Anthropic keys)
python -m xrf rebuild               # regenerate every figure from stored raw data, offline, no spend
python -m xrf costs                 # spend against caps
```

## Working rules

- Keep `docs/STATUS.md` current (Current facts, In progress, Waiting on Alex) and log every design choice
  in `docs/DECISIONS.md` with a date.
- British English in prose.
