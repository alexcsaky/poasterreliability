# Status

_Last updated 2026-11-20._

## Current facts

- Pipeline code for Stages 1–9 is written (`xrf/`), with offline tests on a fake X/LLM world (`python -m pytest -q`).
- No API keys are present in this environment: `X_BEARER_TOKEN`, `XAI_API_KEY` and `ANTHROPIC_API_KEY` are all unset.
  Everything that needs no key is being done; Stages 2–8 cannot run until the X and Anthropic keys are provided.
- X API facts and prices were checked against the official docs on 2026-11-20 (D-002, `docs/api_docs_findings.md`).
- Spend so far: 0 USD on every budget.

## In progress

- Stage 1 ledger: research agents finishing; merge, validation, 20% re-research, then tag `rules-v1`.

## Waiting on Alex

- Keys (see the end of the session summary).
