# What broke

## First live run (2026-11-21)

- **X credits ran out during cohort discovery.** After 33.44 USD of metered X reads (2.70 signals, 30.74 discovery;
  worst-case pricing that bills expansions, so the real X bill is probably lower) X returned HTTP 402
  `credits-depleted`. The prepaid balance on the X account was smaller than the caps. Stage 2 stopped after the
  per-release sweeps; no cohort, no collection. Resumes at no extra cost once credits are added (D-022).
- **Re-runs were not making identical requests.** Search terms of equal length were ordered by hash, so each
  run's query differed and missed the store. Fixed and the stored responses re-linked at no cost (D-023).
- **X credit still depleted on 2026-11-23** despite auto-recharge being expected.
- **No Anthropic key.** `ANTHROPIC_API_KEY` was empty, so extraction, resolution, the audit re-run and the report
  could not run even with X credit.
- **Tests made real Grok calls** when a real `XAI_API_KEY` was in the environment: about 4.18 USD over four test
  runs, outside the project meter. Fixed in `tests/conftest.py`.
- **`data/raw/` was not git-ignored.** Fixed; nothing was committed.
- **Official X signals are uneven.** `signals-x` found 310 posts, but many releases have none in the 21 days
  before release (e.g. OpenAI GPT-5.4 and GPT-5.5). Worth checking whether the official-account list or the
  query misses them before the "before any official signal" figures are trusted.

## Build (2026-11-20)

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
