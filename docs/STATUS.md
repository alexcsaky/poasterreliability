# Status

_Last updated 2026-11-23._

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
- **First live run (2026-11-21) halted in Stage 2** (D-022). The X account's prepaid credit ran out (HTTP 402
  `credits-depleted`) after the per-release discovery sweeps, and `ANTHROPIC_API_KEY` was empty. **No cohort exists
  yet (STOP 1 not reached), no posts collected, no claims, verdicts or report figures.**
- Done live: `probe` (`tweet.fields` confirmed, `field_style: tweet` kept); `signals-x` (310 official pre-release
  posts on X, `ledger/signals_x.csv`); cohort sweeps for every release in the window (5,255 discovery posts,
  3,476 candidate accounts, 134 stored pages). Not done: Grok discovery, lookups, activity floor, ranking, pilot pick.
- **Spend (project meter, worst-case pricing that bills expansions):** X reads 2.70 / 150 USD, discovery
  30.74 / 75 USD, model calls 0.00 / 75 USD. Separately, about **4.18 USD of real xAI spend outside the meter**:
  test runs made real Grok calls while a real `XAI_API_KEY` was set (fixed in `tests/conftest.py`).
- The run is resumable at no cost: stored 2xx responses are replayed, `cohort_as_of` is fixed at 2026-11-21T19:00Z.
  A bug that made re-runs build differently ordered queries (and so pay again) was fixed on 2026-11-23 (D-023).
- **Resumed 2026-11-23:** all 68 stored sweeps replayed free; the first new request still got HTTP 402
  `credits-depleted`. `ANTHROPIC_API_KEY` is saved on the environment but still empty in this session's container.
- **X API facts were checked against the official docs** (D-002, `docs/api_docs_findings.md`): posts $0.005 and
  users $0.010 per object; full-archive search available on pay-per-use; user timelines stop at 800 posts when
  replies are excluded, so collection uses full-archive search (D-003); `impression_count` is public.

## In progress

- Nothing running. Blocked on X credit and the Anthropic key (below).

## Waiting on Alex

1. **X credit and the Anthropic key.** X still reports credits depleted (auto-recharge did not fire; check it in
   the X developer console). `ANTHROPIC_API_KEY` is saved on the environment but not visible in this session's
   container (saved variables load at session start). The X balance ran out at about 33 USD of metered reads. To
   finish the pilot within the caps the account needs up to about 44 USD more for discovery plus up to 147 USD for
   collection (worst case; actual likely lower). `ANTHROPIC_API_KEY` was empty in this session. Then
   `python -m xrf pilot` resumes from the stored responses; the cohort summary and 15 pilot accounts will be added
   here at STOP 1 and the run will continue with the pilot only.
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
