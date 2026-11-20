# Status

_Last updated 2026-11-20._

## Current facts

- **Stage 1 is done.** `ledger/releases.csv` has 259 release events from 1 Dec 2025 to 20 Nov 2026 (Alibaba 53,
  Google DeepMind 54, OpenAI 49, xAI 20, Mistral 19, Zhipu 18, Anthropic 16, Meta 14, DeepSeek 11, Moonshot 5;
  66 flagship). `ledger/signals.csv` has 98 official pre-release signals. Every row has an official source;
  `python -m xrf ledger-validate` reports 0 problems. Caveats: `ledger/NOTES.md`.
- **Ledger re-research:** a random 20% (52 rows) was researched again independently. Field-level disagreement
  14.0% (308 fields compared). Real conflicts (not a value only one side found, not a one-day date difference)
  2.6%, all definitional (which date counts as the announcement, native vs extended context, price bases).
  Details: `ledger/reresearch/report.md`, D-020.
- **`RULES.md` is frozen as `rules-v1`** (annotated tag created locally; `RULES.lock` committed because this
  session cannot push tags; D-021). Resolution refuses to run if `RULES.md` changes without a dated DECISIONS entry.
- **Stages 2–9 are built and tested** (`xrf/`, `python -m xrf -h`). 18 offline tests run the whole pipeline on a
  fake X/LLM world, including cap refusal, span validation, the daily job with hashes and commits, deletion
  checks, and an offline `rebuild` that reproduces the report byte for byte with no calls and no spend.
- **No API keys were available**, so Stages 2–8 have not run against real data: there is no cohort yet (STOP 1 not
  reached), no posts, claims or verdicts. `report/pilot.md` exists in its no-data form. Spend: 0 USD on every budget.
- **X API facts were checked against the official docs** (D-002, `docs/api_docs_findings.md`): posts $0.005 and
  users $0.010 per object; full-archive search available on pay-per-use; user timelines stop at 800 posts when
  replies are excluded, so collection uses full-archive search (D-003); `impression_count` is public.

## In progress

- Nothing running. The next step needs keys (below).

## Waiting on Alex

1. **Keys.** Set `X_BEARER_TOKEN` (X pay-per-use credits; the pilot can spend at most 150 USD of X reads + 75 USD of
   discovery) and `ANTHROPIC_API_KEY` (at most 75 USD). `XAI_API_KEY` is optional (Grok, for cohort discovery only).
   Then:
   ```bash
   python -m xrf probe     # one ~0.01 USD call: confirms tweet.fields vs post.fields (D-002)
   python -m xrf pilot     # signals-x, cohort (STOP 1 output), collection, extraction, resolution, audit, report; stops at STOP 2
   ```
   The cohort and pilot subset will land in `cohort/` for you to look over; the run continues with the 15 pilot
   accounts only, as the brief says.
2. **Terms of use (D-017), before the pilot runs.** X's pay-per-use agreement bars providing licensed content "to
   any third party except as expressly permitted"; sending post text to Anthropic for extraction may fall under it.
   Public datasets may contain post IDs only, not text. Naming accounts in analysis is not addressed.
3. **Push the `rules-v1` tag** after merging this branch (`git push origin rules-v1`, or tag the merge commit).
4. **Check `config/lab_staff.yaml`** (seeded from memory) and, once the cohort exists, `cohort/excluded.csv`
   (bio-based staff exclusions are heuristic).
5. **Self-thread continuations** are left out as replies (D-011). Include them?
6. **Baseline look-back** is truncated by the ledger's 1 Dec 2025 start (about 9–11.5 months for pilot claims,
   not 12; D-014). Extend the ledger back to Aug 2025?
7. **Ledger judgement calls** (`ledger/NOTES.md`): tiers (e.g. Gemini 4 Neon, Muse Spark Open), and whether models
   limited to approved organisations (Mythos, GPT-Rosalind) stay `preview` (not "released" for ordinary users).
8. **Daily job:** where to publish the daily hash line so it is a public timestamp (D-016), and when to schedule it.
   Not scheduled.
9. **Raw data home:** `data/raw/` (the evidence for every figure) is not in git; decide where it lives (D-005).
