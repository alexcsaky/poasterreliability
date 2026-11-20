"""LLM calls (Anthropic Messages API) through the cost meter and raw store.

Structured output via output_config.format (JSON schema). Responses are cached by request, so a
re-run or `xrf rebuild` reuses the stored response instead of paying again."""
from __future__ import annotations

import json
import sqlite3
import time

from . import config, costs, rawstore

BUDGET = "model_calls"


def _price(model: str) -> tuple[float, float]:
    p = costs.pricing("anthropic")["models"][model]
    return p["input_per_mtok_usd"] / 1e6, p["output_per_mtok_usd"] / 1e6


def worst_case(model: str, system: str, content: list, max_tokens: int) -> float:
    pin, pout = _price(model)
    n_img = sum(1 for b in content if b.get("type") == "image")
    chars = len(system) + len(json.dumps(content, ensure_ascii=False))
    in_tok = chars / 3 + n_img * costs.pricing("anthropic").get("image_tokens_estimate", 1600) + 50
    return in_tok * pin + max_tokens * pout


def actual_cost(model: str, body: bytes) -> tuple[float, float, str]:
    pin, pout = _price(model)
    u = json.loads(body).get("usage", {}) or {}
    tin = (u.get("input_tokens") or 0) + 1.25 * (u.get("cache_creation_input_tokens") or 0) \
        + 0.1 * (u.get("cache_read_input_tokens") or 0)
    tout = u.get("output_tokens") or 0
    return tin * pin + tout * pout, (u.get("input_tokens") or 0) + tout, "tokens"


class LLMError(RuntimeError):
    pass


def structured(conn: sqlite3.Connection, *, role: str, system: str, content: list, schema: dict,
               prompt_version: str, model: str | None = None) -> tuple[dict | None, rawstore.Raw]:
    """Run one structured-output call. role selects the model block in config/models.yaml.
    Returns (parsed_json_or_None, raw). None means refusal or unparseable output (recorded)."""
    mcfg = dict(config.load("models")[role])
    model = model or mcfg["model"]
    params = {"model": model, "system": system, "content": content, "schema": schema,
              "effort": mcfg.get("effort"), "max_tokens": mcfg["max_tokens"], "prompt_version": prompt_version}

    def do_request():
        return _send(model, system, content, schema, mcfg)

    raw = rawstore.call(conn, provider="anthropic", endpoint="messages", params=params, budget=BUDGET,
                        worst_case_usd=worst_case(model, system, content, mcfg["max_tokens"]),
                        do_request=do_request, cost_of=lambda s, b: actual_cost(model, b))
    return parse(raw.body), raw


def _send(model: str, system: str, content: list, schema: dict, mcfg: dict) -> tuple[int, bytes]:
    """The only function that talks to the provider (replaced in tests)."""
    import anthropic
    if not config.env_key("ANTHROPIC_API_KEY") and not config.env_key("ANTHROPIC_AUTH_TOKEN"):
        raise LLMError("ANTHROPIC_API_KEY is not set")
    client = anthropic.Anthropic(max_retries=4)
    output_config = {"format": {"type": "json_schema", "schema": schema}}
    if mcfg.get("effort"):
        output_config["effort"] = mcfg["effort"]
    for attempt in range(5):
        try:
            r = client.messages.with_raw_response.create(
                model=model, max_tokens=mcfg["max_tokens"], system=system,
                messages=[{"role": "user", "content": content}], output_config=output_config)
            return r.status_code, r.read()
        except anthropic.RateLimitError:
            time.sleep(10 * (attempt + 1))
        except anthropic.BadRequestError as e:
            return 400, json.dumps({"error": str(e)}).encode()
    raise LLMError("rate limited repeatedly")


def parse(body: bytes) -> dict | None:
    msg = json.loads(body)
    if msg.get("stop_reason") in ("refusal", "max_tokens") or "content" not in msg:
        return None
    for block in msg["content"]:
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                return None
    return None
