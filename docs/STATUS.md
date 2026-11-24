# Status

_Last updated 2026-11-24._

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
- **Stage 2 cohort built (2026-11-24): 100 accounts** (107 passed; top 100 by median impressions). Bar (D-025,
  D-026): at least 2 posts naming a ledger model before its announcement (from per-release and flagship pre-launch
  sweeps) or a seed account; at least 1,000 followers; not lab staff; at least 10 strict-rule release posts in
  90 days. Pool 4,477; 176 met the pre-release requirement; 16 of the 19 seeds are in (out: @legit_api and
  @apples_jimmy on the activity floor, @chatgpt21 does not exist). 13 of the top 22 are seeds; @kimmonismus is #1,
  @iruletheworldmo #10. Files: `cohort/`.
- **Collection (Stage 3) started 2026-11-24, stopped by X credits running out:** @marcthecreatorr and @Ananth7e
  complete, @NFT_Chen partial (2,282 posts), 17 accounts to go. About 0.009 USD per collected post including
  quoted posts and authors. X reads 42.23 / 150 USD.
- **Pilot accounts (superseded by D-027, see `cohort/pilot.csv`; 15 random + 5 named):** top: @ArtificialAnlys, @NFT_Chen, @ChrisGPT, @morganlinton, @marcthecreatorr; middle:
  @laopai1990, @Its_lakshya_ai, @mrfanduu, @hakmgpt, @gadi_neelesh; bottom: @AI_Screening, @R2Cdev_, @glitch_catAI, @MRehan_5, @melophile0646. **Not yet collected.**
- The pre-release count still undercounts (relevance-ranked samples of 100 posts per release), which is why the
  known leakers needed seeding.
- Done live: `probe` (`tweet.fields` confirmed); `signals-x` (310 official pre-release posts, `ledger/signals_x.csv`).
- **Spend (project meter):** X reads 2.70 / 150 USD, discovery 91.17 / 100 USD (cap raised from 75 by Alex,
  D-025), model calls 0.00 / 75 USD. Separately about 4.18 USD of xAI spend outside the meter from test runs (fixed).
- Fixed along the way: X out of credit (topped up); non-deterministic query order (D-023); ranking slimmed to fit
  (D-024); candidate pool inflated by re-runs (D-025). `ANTHROPIC_API_KEY` is still empty in this session.
- **X API facts were checked against the official docs** (D-002, `docs/api_docs_findings.md`): posts $0.005 and
  users $0.010 per object; full-archive search available on pay-per-use; user timelines stop at 800 posts when
  replies are excluded, so collection uses full-archive search (D-003); `impression_count` is public.

## In progress

- Nothing running. Cohort built; collection waits for Alex to confirm the pilot subset (below).

## Waiting on Alex

1. **Pilot subset and the Anthropic key.** Confirm the random pilot (or ask for named forecasters in it) before
   collection. `ANTHROPIC_API_KEY` is saved on the environment but empty in this session's container.
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
10. **Official X signals look uneven.** `ledger/signals_x.csv` has 310 posts, but many releases (e.g. OpenAI GPT-5.4,
    GPT-5.5) show none in the 21 days before release. Worth a look at the official-account list before the
    "before any official signal" figures are trusted (`report/what_broke.md`).
