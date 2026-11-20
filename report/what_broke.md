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
