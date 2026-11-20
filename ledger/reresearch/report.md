# Ledger re-research check

A random 52 of 259 ledger rows (seed 20261120) were researched again from official sources by researchers who saw only the lab and model name. Fields compared at day level (dates), exact numbers (price), 2% (context window), 0.15 points (benchmarks in common).

| release_id | field | first pass | second pass | result |
|---|---|---|---|---|
| alibaba-qwen-audio-3-0-tts | announced_at | 2026-07-14 | 2026-07-20 | conflict (6 days) |
| alibaba-qwen-audio-3-0-tts | price |  | qwen-audio-3.0-tts-flash $0.15/10k chars; qwen-audio-3.0-tts-plus $0.2/10k chars (Model Studio Singapore, International) | one blank |
| alibaba-qwen-audio-3-0-tts | benchmarks |  | WER/CER avg (Flash)=3.87; WER/CER avg (Plus)=3.96; Speaker similarity avg (Plus)=82.75; Speaker similarity avg (Flash)=80.44; Artificial Analysis TTS leaderboard (Plus)=#1 | one blank |
| alibaba-qwen-image-3-0 | announced_at | 2026-07-20 | 2026-07-21 | off by 1 day |
| alibaba-qwen-image-3-0 | price | qwen-image-3.0-pro: $0.04/image (1k), $0.075/image (2k); qwen-image-3.0: $0.03/image (1k) (International (Singapore) list price per Model Studio pricing page as retrieved 2026-11-20 (may differ from launch price)) | qwen-image-3.0-pro: input $0.003/image, output $0.04/image (1K) or $0.075/image (2K); qwen-image-3.0: input $0.003/image, output $0.03/image (Model Studio Singapore, International) | conflict (different price bases) |
| alibaba-qwen3-5-ocr | price | input $0.069, output $0.275 per Mtok (China list, USD) | input CNY 0.5/Mtok ($0.069); output CNY 2/Mtok ($0.275) (China (Beijing) region only) | conflict (different price bases) |
| alibaba-qwen3-5-ocr | context_window |  | 65536 | one blank |
| alibaba-qwen3-7-flash | context_window |  | 1000000 | one blank |
| alibaba-qwen3-8-2-4t-a95b | context_window | 262144 native (extensible to 1010000) | 1000000 | conflict (262144 vs 1e+06) |
| alibaba-qwen3-8-flash | price | qwen3.8-flash: input $0.15/Mtok, output $0.47/Mtok (International (Singapore) list price per Model Studio pricing page as retrieved 2026-11-20 (may differ from launch price)) | input $0.16/Mtok; output $0.47/Mtok (QwenCloud, per launch blog: CNY 1 / CNY 3) | conflict {'input': (0.15, 0.16), 'output': (0.47, 0.47)} |
| alibaba-qwen3-8-max | announced_at | 2026-08-02 | 2026-08-03 | off by 1 day |
| alibaba-qwen3-omni-flash-2025-12-01 | announced_at | 2025-12-08T21:00:00Z | 2025-12-09 | off by 1 day |
| alibaba-qwen3-omni-flash-2025-12-01 | price |  | input: text $0.43, audio $3.81, image/video $0.78 per Mtok; output: text $1.66 (text-only input) / $3.06 (multimodal input), text+audio $15.11 per Mtok (qwen3-omni-flash, Model Studio Singapore, International) | one blank |
| alibaba-qwen3-omni-flash-2025-12-01 | context_window |  | 65536 | one blank |
| alibaba-qwen3-omni-flash-2025-12-01 | benchmarks |  | ZebraLogic (vs Qwen3-Omni-Flash)=+5.6; LiveCodeBench-v6 (vs Qwen3-Omni-Flash)=+9.3; MMMU (vs Qwen3-Omni-Flash)=+4.7; MMMU-Pro (vs Qwen3-Omni-Flash)=+4.8; VoiceBench (vs Qwen3-Omni-Flash)=+3.2 | one blank |
| zhipu-glm-5 | announced_at | 2026-02-12 | 2026-02-11 | off by 1 day |
| zhipu-glm-5 | consumer_available_at | 2026-02-12 | 2026-02-11 | off by 1 day |
| zhipu-glm-5 | api_available_at | 2026-02-12 | 2026-02-11 | off by 1 day |
| zhipu-realvideo | open_weights_at | 2025-12-12 | 2025-12-11 | off by 1 day |
| anthropic-claude-mythos-5-1 | api_available_at |  | 2026-09-01 | one blank |
| anthropic-claude-mythos-5-1 | preview_at | 2026-09-01 |  | one blank |
| anthropic-claude-mythos-5-1 | status | preview | released | preview vs released |
| meta-muse-wonder-full | context_window |  | 1000000 | one blank |
| google_deepmind-antigravity-agent | context_window |  | 1048576 | one blank |
| google_deepmind-gemini-3-5-transcribe | consumer_available_at |  | 2026-08-26 | one blank |
| google_deepmind-gemini-3-5-transcribe | price | Transcribe: audio in $2/Mtok, text out $12/Mtok (~$0.005/min); Transcribe Live: $3.50/$21 (~$0.009/min) | gemini-3.5-transcribe: input $2.00/Mtok audio (~$0.003/min); output $12.00/Mtok text; live: input $3.50/Mtok, output $21.00/Mtok | conflict (different price bases) |
| google_deepmind-gemini-3-deep-think | preview_at | 2025-11-18 |  | one blank |
| openai-gpt-5-3-codex | preview_at | 2026-02-09 |  | one blank |
| openai-gpt-5-3-codex | benchmarks |  | Terminal-Bench 2.0=77.3%; SWE-Bench Pro (Public)=56.8%; OSWorld-Verified=64.7% | one blank |
| openai-gpt-5-4-pro | benchmarks |  | BrowseComp=89.3%; ARC-AGI-2 (Verified)=83.3%; FrontierMath Tier 1-3=50.0%; FrontierMath Tier 4=38.0%; Humanity's Last Exam (with tools)=58.7%; GDPval=82.0% | one blank |
| openai-gpt-5-5 | benchmarks |  | Terminal-Bench 2.0=82.7%; SWE-Bench Pro=58.6%; OSWorld-Verified=78.7%; GDPval=84.9%; GPQA Diamond=93.6%; BrowseComp=84.4% | one blank |
| openai-gpt-5-5-pro | consumer_available_at |  | 2026-04-23 | one blank |
| openai-gpt-5-5-pro | benchmarks |  | BrowseComp=90.1%; FrontierMath Tier 1-3=52.4%; FrontierMath Tier 4=39.6%; Humanity's Last Exam (no tools)=43.1%; Humanity's Last Exam (with tools)=57.2% | one blank |
| openai-gpt-6-luna | benchmarks |  | DeepSWE v1.1 (max effort)=66.6% | one blank |
| openai-gpt-6-rosalind | benchmarks |  | MedChemBench v7=49.6%; GeneBench Pro v13=37.7%; LifeSciBench Gold=61.3% | one blank |
| openai-gpt-rosalind | api_available_at |  | 2026-09-08 | one blank |
| openai-gpt-rosalind | status | preview | released | preview vs released |
| openai-gpt-rosalind | benchmarks |  | BixBench (pass@1)=0.751 | one blank |
| xai-grok-4-3 | benchmarks |  | Artificial Analysis Omniscience=#1 (lowest hallucination rate among frontier models); Artificial Analysis Tau2 Telecom=#1; Vals AI Case Law=#1; Vals AI Corporate Finance=#1 | one blank |
| xai-grok-build-0-1 | consumer_available_at | 2026-05-25 | 2026-05-14 | conflict (11 days) |
| xai-grok-imagine-1-0 | announced_at | 2026-01-28 | 2026-02-02T03:29:07Z | conflict (5 days) |
| xai-grok-imagine-video-1-5 | benchmarks |  | Video 1.5 Fast generation time 6s 720p=~25s (previous model 40+s) | one blank |
| xai-grok-voice-transcribe-2-0 | announced_at | 2026-09-17 | 2026-09-18T17:47:40Z | off by 1 day |

## Summary

| field | compared | disagree |
|---|---|---|
| announced_at | 52 | 7 |
| api_available_at | 46 | 3 |
| status | 52 | 2 |
| price | 43 | 6 |
| benchmarks | 36 | 11 |
| context_window | 34 | 6 |
| consumer_available_at | 25 | 4 |
| open_weights_at | 11 | 1 |
| preview_at | 9 | 3 |

Field-level disagreement: 43/308 = 14.0%. Rows with any disagreement: 27/52 = 51.9%.

Disagreements are of three kinds: one researcher found a value the other did not (`one blank`), dates one day apart (usually a time-zone or blog-vs-changelog difference), and real conflicts. Real conflicts only: 8/308 = 2.6% of fields; rows with a real conflict 8/52 = 15.4%.
