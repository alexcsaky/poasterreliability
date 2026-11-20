"""Run state that must stay fixed across re-runs (e.g. the pilot's as-of time), so that every request
is identical on resume and is served from the raw cache instead of being bought again."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import config

PATH = config.ROOT / "config" / "run_state.json"


def _load() -> dict:
    return json.loads(PATH.read_text()) if PATH.exists() else {}


def get(key: str, default=None):
    return _load().get(key, default)


def get_or_set_time(key: str) -> datetime:
    s = _load()
    if key not in s:
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        s[key] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        PATH.write_text(json.dumps(s, indent=2, sort_keys=True) + "\n")
    return datetime.fromisoformat(s[key].replace("Z", "+00:00"))


def set(key: str, value) -> None:
    s = _load()
    s[key] = value
    PATH.write_text(json.dumps(s, indent=2, sort_keys=True) + "\n")
