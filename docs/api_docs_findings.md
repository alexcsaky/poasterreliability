# X API v2 (pay-per-use) and xAI X Search: findings from the official docs

All sources were accessed on **2026-11-20**. Each page was fetched as raw Markdown (docs.x.com and docs.x.ai serve any page as `.md`), or from the sites' `llms-full.txt` dumps. Quotes are verbatim. **Not confirmed** means no official page stated the fact; nothing here is filled in from memory.

Note on sources:
- `developer.x.com/#pricing` renders client-side (and WebFetch got HTTP 402), so its numbers could not be read. The docs.x.com pricing page is the source used for prices.
- `developer.x.com/en/developer-terms/agreement-and-policy` redirects to `https://docs.x.com/developer-terms/policy`.
- `x.com/en/developer-terms` is a JS app and its text could not be read. The docs.x.com copies of the terms (Developer Agreement, PPU Agreement, Policy, Restricted Use Cases) are used instead.

---

## 1. Pricing model and unit prices

**Pay-per-use exists, and it is the default self-serve model.**
- "The X API uses **pay-per-usage** pricing. No subscriptions—pay only for what you use." and "Purchase credits upfront in the Developer Console. Credits are deducted as you make API requests." See https://docs.x.com/x-api/getting-started/pricing
- Launch date, from the changelog entry of Feb 6, 2026: "Today, we officially launched **X API Pay-Per-Use** pricing — a flexible credit-based model ... Basic and Pro plans remain available, and existing subscribers can opt in to Pay-Per-Use." See https://docs.x.com/changelog

**Read prices.** "All prices are per resource fetched (reads) or per request (writes/actions)." Reads are "Charged per resource returned in the response." Source: https://docs.x.com/x-api/getting-started/pricing

| Resource (verbatim) | Unit cost (verbatim) |
|---|---|
| Posts: Read | $0.005 per resource |
| User: Read | $0.010 per resource |
| Following/Followers: Read | $0.010 per resource |
| List: Read / Space: Read / Community: Read / Note: Read | $0.005 per resource |
| Like: Read / Mute: Read / Block: Read | $0.001 per resource |

**Counts endpoints.** These are listed under "Write operations", which are "Charged per request":
- "**Counts: Recent** | \$0.005 per request"
- "**Counts: All** | \$0.010 per request"

Source: https://docs.x.com/x-api/getting-started/pricing

**Search and timelines have no separate price.** The Usage & Billing page lists both as places where retrieved posts are counted: "Posts retrieved from these endpoints count toward usage: ... **Search** | Recent search, Full-archive search ... **Timelines** | User posts, User mentions". See https://docs.x.com/x-api/fundamentals/post-cap
- My reading: search and timeline results are billed at **Posts: Read, $0.005 per post returned**. No per-request search fee is listed anywhere.

**Expanded objects (`includes`) are not covered.** No page says whether objects returned through expansions (for example `includes.tweets` for quoted posts, or `includes.users`) are billed as Post or User reads. **Not confirmed.**

**Monthly cap.** "Pay-per-usage plans are capped at **3 million Post reads per monthly billing cycle**. If you need higher volume, upgrade to an Enterprise plan." See https://docs.x.com/x-api/getting-started/pricing

**Minimum purchase.** "No contracts, subscriptions, or minimum spend. Start and stop anytime." See https://docs.x.com/x-api/getting-started/pricing
- No minimum credit purchase amount is stated anywhere. **Not confirmed.**

**Deduplication.**
- "All resources are deduplicated within a **24-hour UTC day window**. If you request and are charged for a resource (such as a Post), requesting the same resource again within that window will not incur an additional charge."
- "The deduplication window resets at midnight UTC"
- "Deduplication is a **soft guarantee**."

Source: https://docs.x.com/x-api/getting-started/pricing

Also: "Retrieving a post again the next day = 1 additional charge". See https://docs.x.com/x-api/fundamentals/post-cap

**Price changes.** "Prices are subject to change. Current rates are always available in the Developer Console and on the developer.x.com pricing page." See https://docs.x.com/x-api/getting-started/pricing

**Other.**
- Usage endpoints: `GET /2/usage/tweets` ("Get Post usage data") and `GET /2/usage/credits` ("Get your Pay-per-use (PPU) credit balance in USD"). See https://docs.x.com/x-api/usage/introduction
- Free credits: "Earn **\$20** in free X API credits when you save your first eligible payment card and complete your first credit purchase, and a match of your first auto-recharge **up to \$50**." See https://docs.x.com/x-api/getting-started/pricing
- xAI credits back: 0% under $200 spend per cycle, 10% from $200, 15% from $500, 20% from $1,000. See https://docs.x.com/x-api/getting-started/pricing

## 2. Full-archive search (`GET /2/tweets/search/all`)

**Availability on pay-per-use: yes.**
- "Full-archive search is available to pay-per-use and Enterprise customers."
- Endpoint table: "`/2/tweets/search/all` | Search complete Post archive | Pay-per-use, Enterprise"

Source: https://docs.x.com/x-api/posts/search/introduction

**Price.** No specific price is published. Posts returned count as Post reads (see Q1), so $0.005 per post returned is my inference. https://docs.x.com/x-api/fundamentals/post-cap

**Rate limit.** "`/2/tweets/search/all` | 1/sec, 300/15min | 1/sec | 10 default, 500 max results; 1024 query length". See https://docs.x.com/x-api/fundamentals/rate-limits

**`max_results`.** OpenAPI: "minimum: 10 / maximum: 500 / default: 10". See https://docs.x.com/x-api/posts/search-all-posts
- An old changelog entry says pages are capped at 100 when requesting `context_annotations`: "you can only pull up to 100 posts with the field per page." See https://docs.x.com/changelog

**Query length.** "Self-serve | 512 characters | 1,024 characters" (recent | full-archive); "Enterprise | 4,096 characters". See https://docs.x.com/x-api/posts/search/integrate/operators

**Default time window.** "By default, results return Posts from the last 30 days. Use `start_time` and `end_time` to search specific periods". See https://docs.x.com/x-api/posts/search/quickstart/full-archive-search

**Operators.**
- "Full-archive search supports all query operators." See https://docs.x.com/x-api/posts/search/quickstart/full-archive-search
- From the operator reference (https://docs.x.com/x-api/posts/search/integrate/operators):
  - "`from:` | Standalone | Matches Posts from a specific user"
  - "`is:retweet` | Conjunction required | Matches Retweets"
  - "`is:reply` | Conjunction required | Matches replies"
  - "`is:quote` | Conjunction required | Matches Quote Tweets"
  - "`lang:` | Conjunction required | Matches Posts classified as a specific language"
  - "`quotes_of_tweet_id:` | Standalone"
  - "`conversation_id:` | Standalone"
  - "`min_likes:`/`min_replies:`/`min_reposts:` ... available with both recent search and full-archive search"
  - "`entity:` ... (recent search only)"

**Change on May 4, 2026.** "we migrated the X API v2 search endpoints (`/2/tweets/search/recent`, `/2/tweets/search/all`, `/2/tweets/counts/recent`, `/2/tweets/counts/all`) to the new X core platform search index ... Note: retweets are no longer returned in keyword-based search results". See https://docs.x.com/changelog

**Recent search, for comparison.** "Search Posts from the **last 7 days**. Available to all developers."; `max_results` 10–100; rate limit 450/15min per app. See https://docs.x.com/x-api/posts/search/introduction and https://docs.x.com/x-api/fundamentals/rate-limits

**Counts.**
- `/2/tweets/counts/all`: "300/15min | — | 1024 query length". See https://docs.x.com/x-api/fundamentals/rate-limits
- `granularity` enum is `minute`, `hour`, `day` (default `hour`). Security for counts/all is `BearerToken` only. See https://docs.x.com/x-api/posts/get-count-of-all-posts
- Price: $0.010 per request (counts/all) and $0.005 per request (counts/recent).

## 3. User posts timeline (`GET /2/users/:id/tweets`)

**How far back it goes.**
- "Up to 3,200 most recent Posts". See https://docs.x.com/x-api/posts/timelines/introduction
- Volume limits table: "User Posts timeline | 3,200 most recent"; **"User Posts (exclude=replies) | 800 most recent"**; "Requesting Posts beyond these limits returns a successful response with no data." See https://docs.x.com/x-api/posts/timelines/integrate

**`exclude`.** OpenAPI enum: `replies`, `retweets`. Example: "curl \"https://api.x.com/2/users/123/tweets?exclude=retweets,replies\"". See https://docs.x.com/x-api/users/get-posts and https://docs.x.com/x-api/posts/timelines/integrate

**`start_time` / `end_time`.**
- Supported, with the description "Must be on or after 2010-11-06."
- Also "When both are provided, `start_time` must be earlier than `end_time`."
- `since_id` and `until_id` are also supported.

Source: https://docs.x.com/x-api/users/get-posts

**`max_results`.** "minimum: 5 / maximum: 100". See https://docs.x.com/x-api/users/get-posts
- "Timelines return up to 100 Posts per request." See https://docs.x.com/x-api/posts/timelines/integrate

**Rate limit.** "`/2/users/:id/tweets` | 10,000/15min | 900/15min" (per app | per user). See https://docs.x.com/x-api/fundamentals/rate-limits

**Price.** Posts: Read at $0.005 per post. Owned Reads at $0.001 apply only "when `{id}` matches the authenticated user and that user is the owner of the developer app". See https://docs.x.com/x-api/getting-started/pricing

**Auth.** "User Posts timeline | ✓ | ✓" (App-Only | User Context). See https://docs.x.com/x-api/posts/timelines/integrate

## 4. `impression_count` and `public_metrics`

**Public, available with app-only auth.**
- "**Public** | Bearer Token | Visible to anyone (impressions, likes, reposts, replies)"
- "Impressions | Public | `public_metrics.impression_count`"
- "`public_metrics` | Bearer Token (any)"

Source: https://docs.x.com/x-api/fundamentals/metrics

**Fields in `public_metrics`.** "Includes `retweet_count`, `reply_count`, `like_count`, `quote_count`, `impression_count`, and `bookmark_count`." See https://docs.x.com/x-api/fundamentals/data-dictionary

**Fields that need user context.**
- "`non_public_metrics` | User context (owned posts only)" and "`organic_metrics` | User context (owned posts only)"
- "**30-day limit**: Non-public, organic, and promoted metrics are only available for posts created within the last 30 days."

Source: https://docs.x.com/x-api/fundamentals/metrics

**Timing and definition.**
- Metrics are "at the time of the request." See https://docs.x.com/x-api/fundamentals/data-dictionary
- Impressions: "Count of times the post appeared on a user's screen. Not unique". See https://docs.x.com/x-api/fundamentals/metrics

**Enterprise-only analytics.** The plan table shows "**Engagement metrics** | Not available | Post and media analytics" (pay-per-use | Enterprise). This refers to the analytics endpoints, not to `public_metrics`. See https://docs.x.com/llms-full.txt (Enterprise vs pay-per-use table, enterprise-api/getting-started/about-x-api)

**Naming discrepancy (see Q6).** The live OpenAPI spec names the field `repost_count`, while the prose docs use `retweet_count`.

## 5. Per-author or per-user charges on post reads

- The pricing page lists only per-resource and per-request rates, plus the Owned Reads discount. It shows **no per-unique-author charge**.
- Owned Reads: "Owned Reads are requests made by your own developer app for your own data ... priced at **\$0.001 per resource**". This is the only author-dependent pricing. See https://docs.x.com/x-api/getting-started/pricing
- **Not confirmed** that no such charge exists; I can only say that none is documented.

## 6. Fields and expansions

**Quoted post text.**
- "`referenced_tweets.id` | Post object(s) | Get quoted/replied-to posts" and "`referenced_tweets.id.author_id` | User object(s) | Get authors of referenced posts". See https://docs.x.com/x-api/fundamentals/expansions
- Timeline edge case: "For Retweets with text over 140 characters, the text field is truncated. Use the `referenced_tweets.id` expansion to get the full text." See https://docs.x.com/x-api/posts/timelines/integrate

**Media URLs.**
- "The object is available for expansion with `?expansions=attachments.media_keys` ... Use the expansion with the field parameter: `media.fields`"
- `url`: "A direct URL to the media file on Twitter."
- `preview_image_url`: "URL to the static placeholder preview of this content."
- `variants` carries the video mp4 URLs.

Source: https://docs.x.com/x-api/fundamentals/data-dictionary

**Long posts.** "**note\_tweet** | object | Contains the full text of a Post for long-form Posts (>280 characters)." See https://docs.x.com/x-api/fundamentals/data-dictionary

**Author metrics.** User `public_metrics`: `"public_metrics": {"followers_count": ..., "following_count": ..., "tweet_count": ..., "listed_count": ...}`. Request it with `expansions=author_id&user.fields=public_metrics`. See https://docs.x.com/x-api/fundamentals/data-dictionary and https://docs.x.com/x-api/fundamentals/expansions

**Discrepancy to test before coding.**
- The prose docs, data dictionary and XDK examples use `tweet.fields`, `note_tweet`, `referenced_tweets.id`, `edit_history_tweet_ids` and `retweet_count`. The docs' own "Naming conventions" also say "Consistent terminology (`retweet_count`, not `repost_count` in fields)".
- The OpenAPI spec version **2.175**, served at both https://docs.x.com/openapi.json and https://api.x.com/2/openapi.json (fetched 2026-11-20), uses different names:
  - query parameter `post.fields`, with enum values including `note_post`, `public_metrics`, `attachments`, `created_at` and `conversation_id`
  - expansions `referenced_posts`, `edit_history_post_ids`, `attachments.media_keys` and `author_id`
  - `PostPublicMetrics` with `repost_count`, `reply_count`, `like_count`, `quote_count`, `bookmark_count` and `impression_count` (all marked required)
- **Not confirmed** which names the live API accepts or returns. Make one cheap test call (about $0.005) and write a parser that accepts both naming schemes.

## 7. Developer Agreement and Policy: redistribution, deletion, AI

The applicable agreement for pay-per-use is the PPU Agreement at https://docs.x.com/developer-terms/ppu-agreement. It incorporates the Developer Policy, Restricted Use Rules and Display Requirements.

**Licence scope (PPU Agreement §II.A).** The licence lets you:
- "Use the X API to integrate X Content into your Services or conduct analysis of the X Content, as explicitly approved by X;"
- "Copy a reasonable amount of and display the X Content on and through your Services to Users, as permitted by this Agreement;"
- "Modify X Content only to format it for display on your Services"

Source: https://docs.x.com/developer-terms/ppu-agreement

**Redistribution: IDs only, apart from small manual shares.**
- "If you provide X Content to third parties, including downloadable datasets or via an API, you may only distribute Post IDs, Direct Message IDs, and/or User IDs (except as described below)." See https://docs.x.com/developer-terms/policy
- Volume of IDs: "In total, you may not distribute more than 1,500,000 Post IDs to any entity ... within any 30 day period unless you have received written permission from X." See https://docs.x.com/developer-terms/policy
- Manual shares (Policy): "developers may provide up to 500 public Posts Objects and/or User Objects to each person who uses your service on a daily basis if this is done via non-automated means (e.g., download of spreadsheets or PDFs)." See https://docs.x.com/developer-terms/policy
- Manual shares (Restricted Use page, which conflicts with the 500 figure): "you may only share up to 50,000 hydrated public Post Objects and/or User Objects per recipient, per day, and should not make this data publicly available (for example, as an attachment to a blog post or in a public Github repository)." See https://docs.x.com/developer-terms/restricted-use-cases
- Rehydration is the recommended route: "the best way to do so is by sharing Post IDs ... which the end user of the content can then rehydrate". See https://docs.x.com/developer-terms/restricted-use-cases

**Public display of posts (Policy).** "If you don't use X for Websites to display content, then you must use the X API to retrieve the most current version available for display. If displayed content ceases to be available through the X API, then you must remove it from your service as soon as reasonably possible, or within 24 hours after the receipt of a removal request". See https://docs.x.com/developer-terms/policy

**Deleted content.**
- Policy: "If you store X Content offline, you must keep it up to date with the current state of that content on X. Specifically, you must delete or modify any content you have if it is deleted or modified on X." See https://docs.x.com/developer-terms/policy
- PPU Agreement §IV.B: "If X Content is deleted, gains protected status, or is otherwise suspended, withheld, modified, or removed ... you will make all reasonable efforts to delete or modify that X Content ... as soon as possible, and in any case within twenty four (24) hours after a written request". See https://docs.x.com/developer-terms/ppu-agreement
- Guidelines: "Content is suspended/removed on X | **24 hours**". See https://docs.x.com/developer-guidelines

**Analysis that names accounts.**
- No clause addresses publishing analysis that names accounts. **Not confirmed.**
- Clauses that apply:
  - PPU §XIV.B (User Protection): "you shall not use, or knowingly display, distribute, or otherwise make X Content, or information derived from X Content, available for purpose of: (a) conducting or providing surveillance or gathering intelligence, including but not limited to investigating or tracking X users or X Content". See https://docs.x.com/developer-terms/ppu-agreement
  - Sensitive inferences are banned: "Never derive or infer, or store derived or inferred, information about a X user's: Health ... Political affiliation or beliefs ...". See https://docs.x.com/developer-terms/restricted-use-cases
  - Benchmarking ban: "You may not use the X API to measure the availability, performance, functionality, or usage of X for benchmarking, competitive, or commercial purposes", for example "Calculate aggregate X Post metrics, such as the total number of Posts posted per day, or the number of account engagements". See https://docs.x.com/developer-terms/policy
  - Policy-violation research: "You may not publicly disclose any research or findings concerning ... X Content that measure, analyze, or attempt to identify behaviors or content which violate X policies without express written permission from X." See https://docs.x.com/developer-terms/policy

**AI training and benchmarking.**
- PPU §III.A(k): "use the X API or X Content to fine-tune or train a foundation or frontier model". See https://docs.x.com/developer-terms/ppu-agreement
- Restricted Use page: "X prohibits any use of the X APIs and/or X Content to fine-tune or train a foundation or frontier model with the exception of Grok." See https://docs.x.com/developer-terms/restricted-use-cases
- Guidelines: "App stores X data to train AI/ML models | | Prohibited (except Grok)". See https://docs.x.com/developer-guidelines
- Using X content to benchmark models: **not confirmed**. It is not addressed explicitly.

**Sending content to a third-party LLM.**
- No clause addresses this. **Not confirmed.**
- The clause that could apply is PPU §III.A(d): "sell, rent, lease, sublicense, distribute, redistribute, syndicate, create derivative works of, assign, or otherwise transfer or provide access to, in whole or in part, the Licensed Material to any third party except as expressly permitted in this Agreement". Whether an LLM inference call counts as "provide access" is a matter of interpretation.

**Scope of pay-per-use.** "Pay-Per-Use access ... is designed for hobbyists, commercial prototyping, early-stage X product integrations, and supporting applications with limited end-users." See https://docs.x.com/developer-terms/policy

**Binding use case.** "Your use case description is binding on you, and any substantive deviation from it may constitute a violation of our rules". See https://docs.x.com/developer-terms/policy

## 8. Checking whether a post still exists

**Post lookup.**
- "Verify availability — Check if a Post still exists or was deleted". See https://docs.x.com/x-api/posts/lookup/introduction
- "If a Post is deleted or from a protected account you don't follow: Single Post lookup returns `404`; Multi-Post lookup omits the Post from results with an `errors` array" (`"title": "Not Found Error"`). See https://docs.x.com/x-api/posts/lookup/integrate
- Batch size: "Retrieve multiple Posts by IDs (up to 100)". Rate limit: "`/2/tweets` | 3,500/15min | 5,000/15min". See https://docs.x.com/x-api/fundamentals/rate-limits
- Price: Posts: Read at $0.005 per resource **returned**. Whether a not-found ID in `errors` is charged is **not confirmed**.

**Batch compliance.**
- "upload datasets of Post IDs or user IDs and receive their current compliance status. Use this to identify deleted Posts, suspended accounts". Actions include `delete`/`deleted` and `rehydrate`/`tweet_edited`. See https://docs.x.com/x-api/compliance/batch-compliance/introduction
- Rate limit: "POST `/2/compliance/jobs` | 150/15min". See https://docs.x.com/x-api/fundamentals/rate-limits
- **Price not confirmed.** It does not appear on the pricing page.

## 9. Authentication

App-only Bearer works for every endpoint the plan needs. The OpenAPI `security` lists `BearerToken` for:
- `/2/tweets/search/all`
- `/2/users/{id}/tweets`
- `/2/tweets` (lookup)
- `/2/users/by` (usernames, max 100 per request)
- `/2/tweets/counts/all` (Bearer **only**)
- `/2/tweets/counts/recent`

Sources: https://docs.x.com/x-api/posts/search-all-posts, https://docs.x.com/x-api/users/get-posts, https://docs.x.com/x-api/posts/get-posts-by-ids, https://docs.x.com/x-api/users/get-users-by-usernames, https://docs.x.com/x-api/posts/get-count-of-all-posts

Related statements:
- "App only Access Token allows a X developer app to access information publicly available on X." See https://docs.x.com/fundamentals/authentication/overview
- "**Per-app limits** | Apply with Bearer Token (app-only)". See https://docs.x.com/x-api/fundamentals/rate-limits
- Bearer cannot read `non_public_metrics` or `organic_metrics`; these need user context and only work on your own posts (see Q4).

---

## 10. xAI: X Search tool for Grok

**The tool exists as `x_search` on the Responses API.**
- "The X Search tool enables Grok to perform keyword search, semantic search, user search, and thread fetch on X". The tool name is "Responses API | `x_search`". See https://docs.x.ai/developers/tools/x-search
- Endpoint: `POST https://api.x.ai/v1/responses`, which is OpenAI-SDK compatible with `base_url="https://api.x.ai/v1"`.
- Request shape: `model`, `input`, `tools=[{"type":"x_search", ...}]`. See https://docs.x.ai/developers/tools/x-search

**Parameters.**
- `allowed_x_handles` "(max 20; 10 in the Vercel AI SDK)"
- `excluded_x_handles`; "`allowed_x_handles` cannot be set together with `excluded_x_handles`"
- `from_date` / `to_date`: "Use `YYYY-MM-DD` for both fields ... Dates in any other format, including full date-times, aren't applied." Range is "from 00:00 UTC on `from_date` up to, but not including, `to_date`."
- `enable_image_understanding` and `enable_video_understanding` (both default false)
- The `max_turns` extra-body option limits search rounds.

Source: https://docs.x.ai/developers/tools/x-search

**Internal functions.** The tool exposes `x_keyword_search` ("Keyword search with X's advanced search operators, sorted by `Top` or `Latest`"), `x_semantic_search`, `x_user_search` and `x_thread_fetch`. "the model decides which of the functions below to call, and how often." See https://docs.x.ai/developers/tools/x-search

**Billing.**
- "X Search is billed at $5 per 1k posts fetched and $10 per 1k user profiles fetched, in addition to token costs". See https://docs.x.ai/developers/tools/x-search
- Pricing table: "X Search | `x_search` | ... | $5 / 1k posts, $10 / 1k profiles". See https://docs.x.ai/developers/pricing
- "X Search is billed per item fetched rather than per call: every post returned by a search or thread fetch, including parent and quoted posts, counts toward the post rate". See https://docs.x.ai/developers/pricing
- Counts appear under `usage.server_side_tool_usage_details` as `x_posts_fetched` and `x_users_fetched`. They "are not de-duplicated; a post returned by two searches counts twice." This applies to pricing "in effect as of September 21, 2026". See https://docs.x.ai/developers/tools/x-search

**Token costs.** "All standard token types are billed for the model used in the request: Input tokens ... Reasoning tokens ... Completion tokens ... Image tokens ... Cached prompt tokens". See https://docs.x.ai/developers/pricing

**Cheapest models (per 1M tokens, under 200k prompt tokens).** These are the lowest text prices on the page. See https://docs.x.ai/developers/pricing

| Model | Input | Cached input | Output | Context |
|---|---|---|---|---|
| `grok-4.3` | $1.25 | $0.20 | $2.50 | 1M |
| `grok-4.20-0309-non-reasoning` | $1.25 | $0.20 | $2.50 | 1M |
| `grok-4.20-0309-reasoning` | $1.25 | $0.20 | $2.50 | 1M |
| `grok-4.7` (flagship, used in all docs examples) | $2.00 | $0.50 | $6.00 | 500k |

- At 200k prompt tokens or more, prices double.
- The Batch API gives 20% off tokens on these models.

**Do the cheap models support `x_search`?**
- `grok-4.20`: yes. Files docs say "Requires models that support agentic tool calling (e.g., `grok-4.20`, `grok-4.5`, `grok-4.6`, `grok-4.7`)" (https://docs.x.ai/llms-full.txt, section /developers/model-capabilities/files/...). The grok-4.20 non-reasoning model page also says "agentic tool calling capabilities" (https://docs.x.ai/developers/models/grok-4.20-0309-non-reasoning).
- `grok-4.3`: the Batch API docs include `{"model": "grok-4.3", "tools": [{"type": "web_search"}, {"type": "x_search"}], ...}` (https://docs.x.ai/developers/advanced-api-usage/batch-api). Its model page lists only "Function calling: Yes" (https://docs.x.ai/developers/models/grok-4.3). Treat this as **likely but not explicitly confirmed**.

**Legacy Live Search.**
- `search_parameters` (with `mode`, `sources`, `from_date`, `to_date`, `max_search_results`) still appears in the Chat Completions API reference. See https://docs.x.ai/developers/rest-api-reference/inference/chat-completions
- No pricing for it is listed, and the tools guide documents only `x_search`. Its current status and price are **not confirmed**. Use `x_search` on `/v1/responses`.

**Rate limits for grok-4.3 / grok-4.20.** "Requests per second | 37" and "Tokens per minute | 10,000,000". See https://docs.x.ai/developers/models/grok-4.3

---

## Implications for the plan (my analysis, not quotes)

1. **Collecting every original and quote post for about 15 accounts over 90 days.**
   - Use `/2/tweets/search/all` with `from:<handle> -is:retweet -is:reply`, a `start_time`/`end_time` window, and `max_results=500`. Rate limit is 1 request/sec.
   - Avoid the user timeline with `exclude=replies`, which is capped at the **800 most recent** posts. That could cut off prolific accounts within 90 days.
   - Quote posts are originals for `-is:reply` purposes; `is:quote` isolates them.
   - Cost: posts × $0.005. For example, 15 accounts × 10 posts/day × 90 days = 13,500 posts, about $67.50, well under the 3M/month cap.
   - Re-fetching later for updated metrics is charged again: dedup covers only the same UTC day.
2. **Cohort discovery.** `x_search` costs $5 per 1k posts and $10 per 1k profiles plus tokens. It is not exhaustive (the model chooses its own queries) and not deduplicated. For counting, use `/2/tweets/counts/all` at $0.01 per request.
3. **Ranking by median impressions.** `impression_count` is public with a Bearer token, but it is a snapshot at request time. Fetch every post at a fixed age, or record the fetch time.
4. **Publishing.**
   - Displaying post text in your own service seems allowed, provided you keep it current and remove deleted posts. A public downloadable dataset must contain IDs only.
   - Naming accounts in analysis is not explicitly addressed. The "tracking X users" and benchmarking clauses are an interpretive risk.
   - Sending post text to a non-xAI LLM is not addressed. §III.A(d) is an interpretive risk.
   - Training or fine-tuning a foundation model on X content is prohibited.
5. **Naming risk.** The prose docs and the live OpenAPI spec disagree (`tweet.fields`/`note_tweet`/`retweet_count` vs `post.fields`/`note_post`/`repost_count`). Verify with one live call.

---

## Machine-readable unit prices (USD, confirmed 2026-11-20)

```yaml
accessed: 2026-11-20
x_api_v2_pay_per_use:
  source: https://docs.x.com/x-api/getting-started/pricing
  billing_basis: "reads per resource returned; writes/actions per request"
  post_read_per_resource: 0.005          # applies to search/recent, search/all, timelines, lookup (per Usage&Billing page)
  user_read_per_resource: 0.010
  following_followers_read_per_resource: 0.010
  list_space_community_note_read_per_resource: 0.005
  like_mute_block_read_per_resource: 0.001
  owned_read_per_resource: 0.001         # only when {id} == authenticated user who owns the app
  counts_recent_per_request: 0.005
  counts_all_per_request: 0.010
  search_recent_extra_per_request: null  # none documented
  search_all_extra_per_request: null     # none documented
  expansions_includes_billing: not_confirmed
  batch_compliance_price: not_confirmed
  not_found_ids_in_lookup_billed: not_confirmed
  monthly_cap_post_reads: 3000000
  minimum_purchase: not_confirmed        # docs say "no minimum spend"
  dedup_window: "24h UTC day (resets 00:00 UTC), soft guarantee"
  rate_limits_app_only:
    search_all: "1/sec, 300/15min; max_results 10-500; query 1024 chars"
    search_recent: "450/15min; max_results 10-100; query 512 chars"
    users_id_tweets: "10000/15min; max_results 5-100; 3200 most recent (800 with exclude=replies)"
    tweets_lookup_multi: "3500/15min; up to 100 ids"
    users_lookup: "300/15min; up to 100 per request"
    counts_all: "300/15min"
xai_api:
  source: https://docs.x.ai/developers/pricing
  x_search_per_1k_posts_fetched: 5.00
  x_search_per_1k_profiles_fetched: 10.00
  x_search_dedup: false
  endpoint: "POST https://api.x.ai/v1/responses  tools=[{type: x_search}]"
  cheapest_models_per_1m_tokens_lt_200k:
    grok-4.3: {input: 1.25, cached_input: 0.20, output: 2.50}            # x_search support: shown in batch example, not stated on model page
    grok-4.20-0309-non-reasoning: {input: 1.25, cached_input: 0.20, output: 2.50}  # agentic tool calling stated
    grok-4.20-0309-reasoning: {input: 1.25, cached_input: 0.20, output: 2.50}
  flagship:
    grok-4.7: {input: 2.00, cached_input: 0.50, output: 6.00}
  batch_discount: 0.20
  legacy_live_search_price: not_confirmed
```
