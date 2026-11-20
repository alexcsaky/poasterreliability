"""Grok X search, used ONLY to suggest candidate account names for the cohort pool (Stage 2).
Nothing Grok returns is used as data: suggested handles are looked up through the official X API and
must pass the same floor as every other candidate. Charged to the `discovery` budget."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from . import config, costs, rawstore

URL = "https://api.x.ai/v1/responses"

PROMPTS = [
    "List the X accounts that most often post predictions, rumours or leaks about WHEN new AI models from OpenAI, "
    "Anthropic, Google DeepMind, xAI, Meta, Mistral, DeepSeek, Qwen, Zhipu or Moonshot will be released. Exclude "
    "official lab accounts and lab employees. Return only a list of @handles, one per line, up to 60.",
    "List independent X accounts (not labs, not lab staff) that regularly post about upcoming AI model releases: "
    "model names, codenames, benchmark leaks, pricing, release dates. Return only @handles, one per line, up to 60.",
    "Which X accounts had the most-viewed posts about upcoming or just-released AI models (GPT, Claude, Gemini, Grok, "
    "Llama, Qwen, DeepSeek, Kimi, GLM, Mistral) in the period? Exclude official accounts and staff. Return only "
    "@handles, one per line, up to 60.",
]


def _worst(p: dict) -> float:
    n = p.get("max_posts_per_call_assumed", 200)
    return 60_000 * p["input_per_mtok_usd"] / 1e6 + 8_000 * p["output_per_mtok_usd"] / 1e6 \
        + n * p["x_search_per_post_usd"] + (n // 4) * p["x_search_per_profile_usd"]


def _cost(status: int, body: bytes) -> tuple[float, float, str]:
    p = costs.pricing("xai")
    d = json.loads(body)
    u = d.get("usage") or {}
    tin = u.get("input_tokens") or u.get("prompt_tokens") or 0
    tout = u.get("output_tokens") or u.get("completion_tokens") or 0
    det = u.get("server_side_tool_usage_details") or {}
    posts, users = det.get("x_posts_fetched", 0) or 0, det.get("x_users_fetched", 0) or 0
    usd = tin * p["input_per_mtok_usd"] / 1e6 + tout * p["output_per_mtok_usd"] / 1e6 \
        + posts * p["x_search_per_post_usd"] + users * p["x_search_per_profile_usd"]
    return usd, posts + users, "x_items"


def discover_accounts(conn, as_of: datetime, days: int = 90) -> list[str]:
    import requests
    p = costs.pricing("xai")
    frm, to = (as_of - timedelta(days=days)).strftime("%Y-%m-%d"), as_of.strftime("%Y-%m-%d")
    out: list[str] = []
    for prompt in PROMPTS:
        body = {"model": p["model"], "input": prompt,
                "tools": [{"type": "x_search", "from_date": frm, "to_date": to}]}

        def do_request(body=body):
            r = requests.post(URL, json=body, timeout=300,
                              headers={"Authorization": f"Bearer {config.env_key('XAI_API_KEY')}"})
            return r.status_code, r.content

        raw = rawstore.call(conn, provider="xai", endpoint="/v1/responses", params=body, budget="discovery",
                            worst_case_usd=_worst(p), do_request=do_request, cost_of=_cost)
        if raw.status >= 400:
            continue
        out += handles_from(raw.body)
    return sorted(set(out))


def handles_from(body: bytes) -> list[str]:
    d = json.loads(body)
    texts = []
    for item in d.get("output") or []:
        for c in item.get("content") or []:
            if c.get("type") in ("output_text", "text"):
                texts.append(c.get("text", ""))
    return sorted({h.lower() for h in re.findall(r"@([A-Za-z0-9_]{1,15})\b", "\n".join(texts))})
