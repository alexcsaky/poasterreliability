# Ledger schema

Ground truth for resolution. Every row must cite the lab's own source. No news articles, no leaks,
no third-party trackers as sources (they may be used to *find* an official source, never as one).

## What counts as a release event

A new named model, or a new named version of a model, that the lab makes available to anyone outside
the lab: ordinary paying users, API developers, open-weight download, or a limited preview.
Text, multimodal, reasoning, coding, image, video, audio/speech and agent models are all in scope.
Out of scope: embedding, moderation and reward models; product features that are not a new model;
dated snapshot refreshes that keep the same public name (unless the lab announces them as a new version).
A model announced but not yet shipped by any route gets a row with `status=announced`.

## `ledger/releases.csv`

| column | content |
|---|---|
| release_id | `<lab>-<model-slug>`, lower case, e.g. `openai-gpt-5-1` |
| lab | lab id from `config/labs.yaml` |
| model | official public name, e.g. `GPT-5.1` |
| tier | `flagship` or `other` (see RULES.md, "Tier") |
| modality | `text`, `multimodal`, `reasoning`, `code`, `image`, `video`, `audio`, `agent`, `other` |
| aliases | official alternative names and API ids, `;`-separated |
| codenames | pre-release codenames, `;`-separated, each followed by `(confirmed)` if the lab confirmed it or `(reported)` otherwise |
| announced_at | when the lab first announced the model as released or launching: ISO 8601 UTC (`2025-12-11T18:00:00Z`) or date only (`2025-12-11`) |
| consumer_available_at | date ordinary paying users could use it in the lab's consumer app (blank if never or unknown) |
| api_available_at | date generally available by API to ordinary developers (blank if never or unknown) |
| open_weights_at | date weights were downloadable (blank if not open-weight) |
| preview_at | date of a limited preview for selected testers, if before general availability |
| status | `released` (usable by paying users or API), `preview` (selected testers only), `announced` (not usable yet) |
| price | API price as stated by the lab, e.g. `input $1.25/Mtok; output $10/Mtok`; or consumer plan, e.g. `ChatGPT Plus and above` |
| context_window | tokens as stated by the lab, e.g. `400000` |
| benchmarks | headline figures as stated by the lab, `name=value` pairs `;`-separated, e.g. `SWE-bench Verified=76.3%; GPQA Diamond=88.1%` |
| source_urls | official URLs supporting the row, `;`-separated |
| notes | anything a resolver needs: staggered rollouts, regional limits, which tier of user got it first |

## `ledger/signals.csv`

Official pre-release signals: things a lab, its official accounts, or its staff said before release.

| column | content |
|---|---|
| signal_id | `<release_id>-s<n>` |
| release_id | the ledger row this signal is about (blank if it never shipped and has no row) |
| lab | lab id |
| model_ref | the name used in the signal |
| signal_type | `announced_date`, `teaser`, `staff_hint`, `preview_access`, `roadmap` |
| posted_at | ISO 8601 UTC or date |
| author | account or person, with role (e.g. `@sama (OpenAI CEO)`) |
| text | short verbatim quote |
| url | official URL (lab site, official account, staff member's own account) |
| notes | |
