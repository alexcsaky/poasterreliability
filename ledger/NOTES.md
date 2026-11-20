# Ledger notes

Built 20 Nov 2026 by seven research agents (one per lab or pair of labs), from official sources only, then merged by
`scripts/merge_ledger.py` with the documented edits in `merge_fixes.yaml`. The agents' raw outputs are kept in
`research_batches/`. Row-level doubts are in each row's `notes` column; the points below affect how the ledger
should be used.

## Access limits during research

- openai.com and help.openai.com returned 403 to every fetch; x.com returned 402; web.archive.org was unreachable.
  OpenAI rows rest on developers.openai.com (API changelog, model and pricing pages), system cards and official
  Hugging Face pages. Plan-by-plan ChatGPT rollout dates and many OpenAI headline benchmarks are blank.
- qwen.ai blog pages need JavaScript; Alibaba launch facts come from the official Alibaba Cloud Community copies,
  often dated a day after the original.
- Official X posts were used only where they could be fetched or were quoted on an official page. X-only teasers are
  under-recorded in `signals.csv` (D-008).

## Conventions that differ by lab

- Prices are often today's list price rather than the launch price (Alibaba, Zhipu, Moonshot, some xAI, Meta and
  Google rows); the notes say which.
- Benchmarks published only as chart images were transcribed where possible (Anthropic, Meta) or left blank (some
  Qwen, Zhipu and Google rows).
- Zhipu prints dates in UTC+8; agents recorded the lab's printed date for announcements and the earliest provable
  UTC date for open weights.
- Several Alibaba families released on different days share one row (staggered dates in notes).
- xAI renamed its main X account from @xai to @SpaceXSI (same account id). The current @xai is a different account.
- Meta released no Llama model in the period; its releases are the Meta Superintelligence Labs "Muse" models.
- Anthropic's Mythos models are `status=preview` (verified organisations only) and `tier=flagship`.
- Rows included although announced before 1 Dec 2025, because their first paid release falls inside the period:
  Google's Genie 3 and Gemini 3 Deep Think (Dec 2025 row).

## Judgement calls worth a second look

- Google: Gemini 3 Deep Think's February 2026 upgrade is a separate row with the same name; Gemini 4 Argon/Carbon are
  flagship, Neon/Hydrogen other; Gemini Decision 1 may count as a scoring model and be out of scope.
- OpenAI: tiers (flagship = top model of each generation: GPT-5.2/5.4/5.5 and Pro, 5.6 Sol, 6 Astra, 6.2 Astra);
  circuit-sparsity is a small research model.
- Mistral: Large 4 API date is the public preview (GA later, in notes).
- DeepSeek: V4.1-Pro is `announced` only.
- Meta: Muse Spark Open marked flagship by analogy with the largest Llama release.
- xAI: Grok 4.8 is `preview`, Grok 5 `announced`; unversioned voice API rows are a judgement call.
