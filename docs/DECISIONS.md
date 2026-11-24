# Decisions

Every design choice made while building the pilot, newest last. Each entry is dated. Entries that change
`RULES.md` after the `rules-v1` tag must record the new file's hash as `RULES.md sha256 <first 12 hex>`.

---

## D-001 (2026-11-20) Stack and model provider

- Plain Python 3, SQLite, flat files (CSV/JSONL/Markdown). Dependencies: `anthropic`, `requests`, `PyYAML`,
  `numpy`, `scipy`, `pytest` (`requirements.txt`).
- LLM provider: Anthropic (one key, `ANTHROPIC_API_KEY`). Roles and models are in `config/models.yaml`:
  - pass 1 (is this about a release?): `claude-haiku-5-5`, effort low. Cheapest current model; images included.
  - pass 2 (claim extraction with vision): `claude-sonnet-5-5`, effort medium. Chosen over Opus 5.5 on cost:
    at roughly 3k input / 2k output tokens per release-related post, Opus would put a few thousand posts near
    the 75 USD model-call cap; Sonnet costs half. The cap is enforced either way.
  - name matcher: `claude-sonnet-5-5`, effort low.
  - audit re-run (a different model, as Stage 7 asks): `claude-opus-5-5`, effort medium.
- Structured output via `output_config.format` (JSON schema), so every response parses or is recorded as failed.
- Server-side refusal fallbacks are **not** enabled. A fallback silently swaps the model that produced an
  extraction, which would contaminate the model-agreement audit; a refusal is recorded as a failed extraction
  and counted in the report instead.
- Prices for the cost meter: Anthropic list prices from the claude-api reference cached 2026-11-03
  (Haiku 5.5 $0.10/$0.50, Sonnet 5.5 $2/$10, Opus 5.5 $4/$20 per Mtok).

## D-002 (2026-11-20) X API and xAI: what the official docs say

Checked before any client code was written. Full quotes, URLs and access dates: `docs/api_docs_findings.md`.
Summary:

- **Pricing:** X API pay-per-use (launched 6 Feb 2026), credits, no subscription. Reads are charged per object
  returned: posts $0.005, users $0.010. Counts endpoints: $0.010 per request (full-archive), $0.005 (recent).
  Same object not charged twice in one UTC day ("soft guarantee"). Monthly cap 3M post reads.
  *Not confirmed:* whether objects returned through expansions (`includes.tweets`, `includes.users`) are billed.
- **Full-archive search** (`/2/tweets/search/all`) is available on pay-per-use: 1 request/s, 300/15 min,
  10–500 results per page, 1,024-character queries, `from:`, `-is:retweet`, `-is:reply`, `is:quote`, `lang:`.
  Without `start_time` it searches only the last 30 days. Since 4 May 2026 keyword search no longer returns reposts.
- **User timeline** (`/2/users/:id/tweets`): 3,200 most recent posts, but only the **800 most recent** with
  `exclude=replies`; requests past that return success with no data.
- **Impressions:** `impression_count` is in `public_metrics` and readable with an app-only bearer token.
  It is a snapshot at request time.
- **Per-author charge:** none. (Owned reads at $0.001 apply only to your own account.)
- **Redistribution:** the Developer Agreement/Policy allows sharing post IDs (hydration), not post text, in
  datasets; displayed content must be kept current and deleted posts removed. Training foundation models on X
  content is prohibited. Nothing explicit about naming accounts in analysis or sending post text to a non-X
  LLM; see D-017.
- **Deleted posts:** multi-post lookup omits them and lists them in `errors` ("Not Found Error").
- **Field names:** the guides use `tweet.fields`/`note_tweet`/`referenced_tweets`/`retweet_count`; the live
  OpenAPI spec (v2.175) uses `post.fields`/`note_post`/`referenced_posts`/`repost_count`. The client uses the
  guide names (`field_style: tweet` in `config/pricing.yaml`), the parser accepts both, and `python -m xrf probe`
  settles it with one call (about $0.01) before the pilot.
- **xAI:** `x_search` tool on `POST https://api.x.ai/v1/responses`; $5 per 1,000 posts and $10 per 1,000
  profiles fetched, not de-duplicated, plus tokens. Cheapest suitable model `grok-4.20-0309-non-reasoning`
  ($1.25/$2.50 per Mtok), which the docs state supports agentic tool calling.

## D-003 (2026-11-20) Collection uses full-archive search, not the user timeline

Because of the 800-post cap on timelines with replies excluded (D-002), collection runs
`from:<handle> -is:retweet -is:reply` through full-archive search for the 90-day window, 500 per page, with
expansions for quoted posts, their authors and media. This returns originals and quote posts and leaves out
replies and reposts, as Stage 3 asks. Capture time is the time the raw response was received
(`raw_responses.requested_at`, copied to `posts.captured_at`).

## D-004 (2026-11-20) What each cap covers, and worst-case metering

- `discovery` (75 USD): everything in Stage 2: keyword sweeps, user lookups, counts, ranking reads, Grok.
  Also the one-off `probe` call.
- `x_reads` (150 USD): Stage 3 collection, Stage 9 daily pulls and deletion checks.
- `model_calls` (75 USD): every LLM call (pass 1, pass 2, matcher, audit re-run).
- Before each call the meter checks `spent + worst case <= cap` (worst case = a full page of results, with
  expanded posts and users billed; for LLM calls, estimated input plus `max_tokens` of output). After the call
  it records the actual cost. Because expansion billing is unconfirmed, actual X cost is recorded *as if
  expansions are billed*: recorded spend is an upper bound. Reconcile with the X developer console.

## D-005 (2026-11-20) Raw storage, idempotency, one-command rebuild

- Each external request is keyed by `sha256(provider, endpoint, params)`. A stored successful response for the
  key is reused at no cost. Bodies are stored byte-for-byte (gzip) under `data/raw/<provider>/<date>/`.
- Request parameters that depend on "now" are fixed in `config/run_state.json` the first time they are needed
  (`cohort_as_of`, `pilot_as_of`, `verdict_as_of`), so a resumed or repeated run makes identical requests.
- `python -m xrf rebuild` sets `XRF_OFFLINE=1` (a cache miss is an error, never a network call), clears every
  derived table, re-parses all raw X responses, and re-runs Stages 2–8 from cached responses. The test suite
  checks that a rebuild makes no calls, spends nothing and reproduces the report byte for byte (apart from the
  generation timestamp).
- `data/raw/` is meant to be kept (it is the evidence); `data/xrf.sqlite` is derived and git-ignored.
  Whether raw X responses may be committed to a repo that later becomes public is a terms question (D-017):
  for now they stay out of git; Alex to decide where they live.

## D-006 (2026-11-20) Ledger scope and fields

- Release event: a new named model or named version made available outside the lab (paying users, public API,
  open weights, or limited preview). Text, multimodal, reasoning, code, image, video, audio and agent models are
  in scope; embedding, moderation, reward and classifier models, product features, and same-name snapshot
  refreshes are not (`docs/LEDGER_SCHEMA.md`).
- Open-weight families released at several sizes on one day are one row.
- Added `open_weights_at` and `preview_at` to the fields Stage 1 lists, because "usable" includes open weights
  and a tester preview resolves as partial.
- `status=preview` for models restricted to selected organisations (e.g. Anthropic's Mythos models), even when
  they are production models: ordinary paying users cannot use them.
- Tier: `flagship` = the lab's top general-purpose line (`flagship_lines` in `config/labs.yaml`); see D-019 for
  the per-lab calls made while merging.
- The ledger period starts 1 Dec 2025 as Stage 1 asks. Consequence for baselines: D-014.

## D-007 (2026-11-20) How the ledger was researched and checked

- Seven research agents worked in parallel, one per lab or pair of labs, each reading only official sources
  and writing CSVs in the schema. Discovery via news was allowed; citation was not.
- Validation in code (`python -m xrf ledger-validate`): every row needs at least one source URL on the lab's
  official domains or accounts (`config/labs.yaml`), parseable dates, valid tier/status, and an availability
  date when `status=released`.
- Independent re-research: a random 20% of rows (seed fixed) was given, by lab and model name only, to
  separate agents that had not seen the first pass, who looked up the same fields from official sources.
  Fields are compared in code; the disagreement rate is in `ledger/reresearch/report.md` and the pilot report.

## D-008 (2026-11-20) Official signals: web sources now, X-native signals later

`ledger/signals.csv` holds pre-release signals that can be read on the labs' own websites or are quoted there.
x.com itself cannot be fetched without the API, so teasers posted only on X by official accounts and staff are
under-recorded. This biases the "before any official signal" headline **in favour of** cohort accounts (some
claims will look pre-signal that were not). Fix, once the X key is in: pull the official accounts and listed
staff (`config/labs.yaml`, `config/lab_staff.yaml`) for the days before each release via full-archive search
and add their model mentions as signals. That costs X reads; it is listed for Alex in STATUS.
Implemented as `python -m xrf signals-x` (`xrf/signals_x.py`), run automatically at the start of `xrf pilot`:
flagship releases only, 50 most recent matching posts in the 21 days before each release, written to
`ledger/signals_x.csv` (the resolver reads both signal files). Worst case about 33 USD of the `x_reads` budget
(66 flagship rows, expansions assumed billed); likely far less.

## D-009 (2026-11-20) Resolution rules (RULES.md v1)

Choices made in writing `RULES.md`:
- All times UTC; "week" = ISO week (Mon–Sun); "today" = 24 hours from the post; "tomorrow" = 48 hours.
- "Next week"/"next month": a release *before* the stated period resolves `partial` (early), not correct.
- Named weekday or explicit date: ±12 hours around that UTC day.
- "Soon" is tested at 7, 14 and 30 days; 14 days is the headline, the others are sensitivity columns.
- A claim about a model already released before the post is `uncheckable` (not a forecast).
- Never-shipped models resolve `incorrect` at window end + 14 days (Stage 1).
- Attribute tolerances: exact for price and context window (10% band = partial), ±0.5 points for benchmarks
  (±2 = partial). 128k equals 128,000 or 131,072.
- Questions and jokes are recorded and resolved but excluded from accuracy; they count as vague.
- Hedged and flat claims are scored the same way and reported separately.

## D-010 (2026-11-20) Cohort construction details

- Sweeps: for each ledger release announced in the 90-day window (or up to 7 days before it), full-archive
  search for its names and aliases from 7 days before to 2 days after the announcement, top 100 by relevancy;
  plus up to 10 pages of 500 of generic release talk. Sweeps request posts and quoted posts but **no user
  objects** (users cost twice as much as posts).
- Pool: sweep authors, the authors of posts they quote, and accounts they @mention; plus Grok suggestions if
  `XAI_API_KEY` is set. Grok output is only a list of names; each is looked up through the X API and must pass
  the same floor.
- Lookup only pool members seen at least twice (or suggested by Grok), at most 1,500, to stay inside the
  discovery cap. Single sightings are not looked up.
- "Release-related" for the floor and the ranking is a fixed keyword rule (`xrf/cohort.py`: a model-family term
  AND a release term). It is cruder than pass 1 but costs nothing per post and is the same for every account.
  Counts come from the counts endpoint ($0.01 per call).
- Ranking: median `impression_count` over the 30 most recent release-related original/quote posts aged at least
  3 days (impressions are a snapshot; young posts are under-counted). Ties and missing impressions fall back to
  followers.
- Staff exclusion: handles in `config/labs.yaml`/`config/lab_staff.yaml`, plus a bio heuristic ("at @OpenAI",
  "MTS", "researcher" near a lab name, not preceded by "ex-"/"former"). Every exclusion is written to
  `cohort/excluded.csv` with the matching bio text, for Alex to check. The staff list was seeded from memory and
  needs checking.
- Pilot subset: 5 at random from each third of the ranking, seed 20261119.

## D-011 (2026-11-20) Replies are left out, including self-thread continuations

Stage 3 says to leave out replies. Continuations of an author's own thread are replies in X's data model, so
they are left out too, even though some carry claims. Flagged for Alex: including `in_reply_to_user_id == author`
would be a one-line change in the collection query and extraction filter.

## D-012 (2026-11-20) Extraction details

- One call per post. The extractor gets the author handle, timestamp, post text, quoted post text and author,
  and up to 8 images (post first, then quoted post; videos via their preview frame). Nothing else.
- Pass 1 sees the same input (images are cheap on Haiku). Only pass-1 positives go to pass 2.
- Every field carries a span. The validator (`xrf/extract.py:validate_claim`) requires text spans to occur
  verbatim (whitespace-normalised) in the named source; image spans need a valid image index, a region and the
  visible text; a stated window's phrase must lie inside its span; an attribute's number must appear in its span;
  a relay's account must appear in its span. A claim failing any check is stored with `valid=0` and its reasons,
  and never scored.
- A timing claim with no stated window is stored as `uncheckable` (reason `no_window`); windows are never inferred.
- Posts whose claims were all rejected (`extraction_rejected`) or whose call failed are pipeline failures, not
  vagueness: they are excluded from the vagueness rate and counted in "What broke".

## D-013 (2026-11-20) Resolution details

- Lab is identified from the claim's lab and model text by keyword (`xrf/resolve.py:LAB_WORDS`).
- Name matching: exact (normalised) match on model, aliases and codenames in code; otherwise the matcher model
  sees only the lab and the name and the lab's ledger names. Every match is cached with its reason in
  `alias_matches`.
- Release time = earliest of consumer, API and open-weights dates. "Hours to first official signal" uses the
  earliest of: signals in `signals.csv`, the announcement, the preview, the release.

## D-014 (2026-11-20) Measures

- Accuracy = correct / (correct + incorrect + partial): partial counts as not correct. Wilson 95% intervals.
- Baseline: per Stage 6, the share of daily-start rolling windows of the claim's length in the previous 12 months
  in which the lab released a model of the claimed tier. **The ledger starts 1 Dec 2025, so for claims made before
  1 Dec 2026 the look-back is truncated** (for the pilot window, about 9–11.5 months instead of 12). Extending the
  ledger back to Aug 2025 would fix this; listed for Alex.
- Claimed tier "any" (family claim with mixed tiers) uses releases of either tier.
- Originality: timing claims are clustered by matched release (or normalised name) and overlapping windows; the
  earliest post in a cluster is the originator unless it credits someone else.
- Shrinkage: beta-binomial fitted by maximum likelihood across pilot accounts on all resolved claims (and
  separately on pre-signal timing claims); posterior means reported beside raw figures.
- Ranking: by shrunk accuracy on all resolved claims, only for accounts with at least 20 resolved claims.

## D-015 (2026-11-20) Audit design

- Sample: 200 posts, round-robin across (account × pass-1 decision) strata, so each account and both pass-1
  outcomes are represented as evenly as the data allow. Seed 7.
- Human columns: release-related y/n; counts of missed, invented and wrong-field claims. `audit-score` turns them
  into pass-1 precision/recall and pass-2 precision (with and without wrong fields) and recall.
- Model agreement: pass 2 re-run with `claude-opus-5-5` on the sampled release-related posts; claim-level F1 on
  (family, model, window phrase, attribute, value) and post-level Cohen's kappa on "has a checkable claim".

## D-016 (2026-11-20) Prospective capture timestamping

The daily job writes `prospective/claims/<day>.jsonl`, appends its SHA-256 to `prospective/HASHES.txt` and commits
both. A private git commit is not a public timestamp. To make it one without publishing the claims, the hash
line has to be somewhere public and time-stamped (e.g. a public repo holding only `HASHES.txt`, or an
OpenTimestamps proof). Alex to choose. Scheduling is left to Alex, as asked.

## D-017 (2026-11-20) Terms of use: open questions for Alex

From the docs check (D-002): (a) a public dataset may contain post IDs only, not post text; (b) the
Pay-Per-Use agreement forbids providing "access to ... the Licensed Material to any third party except as
expressly permitted" (§III.A(d)), which could be read to cover sending post text to Anthropic for extraction;
(c) nothing explicitly covers publishing analysis that names accounts. The pipeline is built as specified;
these need a decision (or advice) before the pilot runs and before anything is published.

## D-018 (2026-11-20) Report cost estimate

The full-cohort estimate uses observed pilot rates (posts per account per day, quoted share, release-related
share) when pilot data exist, and states its assumptions otherwise. X cost is shown as a range: posts only, and
posts plus billed expansions (the unconfirmed case).

## D-019 (2026-11-20) Ledger merge edits and tier harmonisation

Applied by `scripts/merge_ledger.py` from `ledger/merge_fixes.yaml`, each with its reason there:
- Dropped 6 rows: GPT-5.1-Codex-Max (usable before the period), and five rows with no official date for any
  availability route (Qwen-Drive-1.0, WebWorld, GLM-5.3-FlashX-Legal, Grok Imagine Image Pro, Grok Imagine Video 1.5
  Lite). Dropped 2 undated signals.
- Tier harmonised so that a lab's smaller or specialised siblings are `other`, as for Gemini Flash vs Pro: DeepSeek
  V4/V4.1 Flash rows and Kimi K2.7 Code set to `other`; Anthropic Mythos rows set to `flagship` (top line; still
  `status=preview`).
- Official domains added after the research showed the labs use them: chatgpt.com, aistudio.google.com (Gemini API
  docs now redirect there), huggingface.co/Wan-AI and github.com/Wan-Video (Alibaba's Wan team), platform.kimi.ai and
  kimi.ai (Moonshot's platform moved), research.meta.ai, dev.meta.ai and huggingface.co/meta-models (Meta), and
  x.com/SpaceXSI (xAI's renamed account). Staff accounts in `config/lab_staff.yaml` count as official for signals;
  added @finkd (Mark Zuckerberg).
- Result: 259 releases, 98 signals, 0 validation problems. Caveats in `ledger/NOTES.md`.

## D-020 (2026-11-20) Re-research result, and filling gaps from the second pass

- 52 of 259 rows (20%, seed 20261120) were re-researched by five agents who saw only lab and model name and were
  told not to open the ledger. 308 fields were comparable. Any disagreement: 14.0% of fields (52% of rows).
  Real conflicts, i.e. not a value only one researcher found and not dates one day apart: 2.6% of fields
  (8 fields; 15% of rows). Full list: `ledger/reresearch/report.md`.
- The real conflicts are definitional rather than errors: which date counts as the announcement (release-notes
  listing vs blog post; Qwen-Audio-3.0-TTS, Grok Imagine 1.0), native vs extended context window (Qwen3.8-2.4T),
  which plan counts as consumer availability (Grok Build 0.1), and price bases (per image vs per token, CNY vs USD,
  $0.15 vs $0.16). No ledger value was changed because of them.
- Comparison rules: dates at day level, price on input/output per-Mtok figures (1% tolerance) or the first dollar
  amount, context window within 5%, benchmarks in common within 0.15 points; text-only prices not compared.
- After the rate was measured, blank fields in the first pass were filled from the second pass where it cited an
  official source: price, context window and benchmarks always, availability dates only where both passes agreed
  on status. 16 rows gained values; each says so in its notes and carries the extra source URLs.

## D-021 (2026-11-20) rules-v1: git tag plus a committed lock file

`RULES.md` was frozen as `rules-v1` on 2026-11-20. The annotated git tag is created locally, but this build
session's git proxy accepts pushes only to the working branch, so the tag could not be pushed. So that a fresh
clone still refuses to resolve against changed rules, `RULES.lock` records the tag name and the SHA-256 of
`RULES.md` at tagging; `xrf/rules.py:assert_rules_tagged` checks the git tag when present and the lock file
otherwise. Alex: push the tag (`git push origin rules-v1`) after merging, or create it on the merge commit.

## D-022 (2026-11-21) First live run: halted at Stage 2 (X credits depleted, no Anthropic key)

- `python -m xrf probe` confirmed `tweet.fields` works; `field_style` stays `tweet`.
- `signals-x` ran: 310 official X pre-release posts written to `ledger/signals_x.csv` (2.70 USD metered).
- `cohort` ran every per-release sweep (5,255 discovery posts, 3,476 candidate accounts, 30.74 USD metered), then
  X answered the next full-archive search with HTTP 402 `credits-depleted`. The X account's prepaid balance ran
  out well below the caps; the meter cannot see the balance, only the caps. Grok discovery, lookups, the activity
  floor, ranking and everything after did not run. No cohort exists yet.
- `ANTHROPIC_API_KEY` was empty in this session, so Stages 4–8 could not have run in any case. The pilot was not
  started with a substitute key.
- Resumption: only 2xx responses are reused from the store, so after a top-up `python -m xrf pilot` (or
  `python -m xrf cohort`) replays the 134 stored pages at no cost and continues from the failed request.
  `cohort_as_of` is fixed in `config/run_state.json` at 2026-11-21T19:00:00Z, so the replay makes identical requests.
- Fixes: `tests/conftest.py` now removes `XAI_API_KEY`. Grok discovery is not faked, so with a real key in the
  environment each test run made three real Grok calls (four runs, about 4.18 USD of xAI spend, recorded only in
  throwaway test databases and not in the project meter). `.gitignore` now excludes all of `data/` (raw
  responses were not ignored before; D-005). A literal `%` in the CLI help text broke `python -m xrf -h`.

## D-023 (2026-11-23) Search-term order made deterministic; stored responses aliased

- Bug: cohort sweeps and `signals-x` built each query from a set of model names sorted by length only. Ties came
  out in hash order, which changes between Python processes, so a re-run built a differently ordered query, missed
  the store and would have paid X again. Found when the resumed `cohort` run asked X for the first sweep again.
- Fix: `xapi.ordered_terms` sorts by (length, text); used by both. Test runs the ordering under six hash seeds.
- `scripts/alias_reordered_queries.py` (run once, no network) replayed both stages and, for each request that
  missed only because of term order, stored the same response body again under the new request key with
  usd=0. 79 requests already matched, 53 were aliased, 4 had no stored response (three sweeps never fetched
  before the 402, and one 0-post signals search whose name selection changed at the cut).
- After the fix the resumed `cohort` replays all 68 per-release sweeps at no cost; the first new request still
  gets HTTP 402 `credits-depleted` (2026-11-23), so X auto-recharge has not happened.

## D-024 (2026-11-23) Ranking sample slimmed to fit the discovery cap

After the X top-up, the broad release sweep, Grok discovery (0.98 USD) and 1,500 user lookups (15 USD) took
discovery spend to 56.25 of 75 USD, and the activity floor (one `counts/all` call per candidate at 0.01 USD)
needs about 5 USD more. Ranking as built fetched 30 posts per passing account with quoted posts expanded
(worst case 0.30 USD each); with about 110 accounts expected to pass, it would have hit the cap partway, wasting
what was spent before the refusal. Before any ranking call was made, the run was stopped and ranking changed to
fetch 20 recent release posts per account with `public_metrics` and referenced-post types only (no expansions;
worst case 0.10 USD). Median impressions over 20 posts instead of 30 is coarser but adequate for a reach ranking.
The cap was not changed.

## D-025 (2026-11-24) Cohort bar tightened; discovery cap raised to 100 USD

Looking at what passed the old bar (254 accounts), Alex and Claude agreed it measured "posts about AI a lot",
not "posts about model releases": the keyword rule accepted generic words (today, available, soon, ship, drop),
ten matching posts in 90 days is about one a week, and content-farm and sponsored accounts passed. Alex decided:
- **Pre-release requirement:** at least 2 original or quote posts naming a ledger model (or its alias or codename)
  before that release's announcement, counted from the stored per-release sweeps (`cohort.pre_release_posts`). Free,
  but it undercounts: each sweep kept the 100 most relevant posts from 7 days before announcement. Only accounts
  meeting it are looked up.
- **Follower floor 1,000** (was 5,000). The pre-release requirement now does the quality filtering.
- **Stricter activity rule** (`STRICT_TERMS`): family term plus a release or forecast word, generic words removed.
  The floor stays at 10 posts in 90 days. Naming each ledger model in the count query is not possible within
  X's 1,024-character full-archive query limit.
- Ranking still uses the broader `release_query` sample (it measures reach, not content), so the 101 ranking
  samples already paid for are reused.
- **Bug fixed:** the candidate pool appended sightings on every run, so after several replays every account looked
  seen 5-10 times and the two-sighting filter did nothing. The pool is now rebuilt from stored responses on each
  run; a test checks a second build is identical and makes no calls.
- **Cap:** discovery raised from 75 to 100 USD by Alex (in chat, 2026-11-24). Other caps unchanged.
- Expect fewer than 100 accounts (the pre-release requirement leaves 127 candidates before other filters).
