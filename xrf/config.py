"""Paths and config loading."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("XRF_ROOT", Path(__file__).resolve().parent.parent))
CONFIG = ROOT / "config"
DATA = Path(os.environ.get("XRF_DATA", ROOT / "data"))
RAW = DATA / "raw"
DB_PATH = DATA / "xrf.sqlite"
LEDGER = ROOT / "ledger"
COHORT = ROOT / "cohort"
AUDIT = ROOT / "audit"
REPORT = ROOT / "report"
PROSPECTIVE = ROOT / "prospective"


@lru_cache(maxsize=None)
def load(name: str) -> dict:
    with open(CONFIG / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def labs() -> list[dict]:
    return load("labs")["labs"]


def lab_by_id() -> dict[str, dict]:
    return {lab["id"]: lab for lab in labs()}


def env_key(name: str) -> str | None:
    v = os.environ.get(name)
    return v if v else None
