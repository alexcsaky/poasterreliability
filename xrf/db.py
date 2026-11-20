"""SQLite storage. Raw API bodies live as gzip files under data/raw; this DB indexes them and
holds everything derived from them. Every derived table can be rebuilt from raw (see `xrf rebuild`)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_responses (
  id INTEGER PRIMARY KEY,
  request_key TEXT NOT NULL,          -- sha256 of provider+endpoint+params
  provider TEXT NOT NULL,             -- x | xai | anthropic
  endpoint TEXT NOT NULL,
  params_json TEXT NOT NULL,
  status INTEGER NOT NULL,
  requested_at TEXT NOT NULL,         -- UTC ISO time the response was received (capture time)
  body_path TEXT NOT NULL,            -- relative to data/, gzip of the exact bytes received
  body_sha256 TEXT NOT NULL,
  usd REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS raw_key ON raw_responses(request_key, status);

CREATE TABLE IF NOT EXISTS cost_events (
  id INTEGER PRIMARY KEY,
  ts TEXT NOT NULL,
  budget TEXT NOT NULL,               -- x_reads | discovery | model_calls
  provider TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  units REAL NOT NULL,
  unit TEXT NOT NULL,
  usd REAL NOT NULL,
  worst_case_usd REAL NOT NULL,
  raw_id INTEGER,
  meta_json TEXT
);

CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  username TEXT, name TEXT, description TEXT,
  followers INTEGER, following INTEGER, tweet_count INTEGER,
  verified INTEGER, created_at TEXT,
  captured_at TEXT, raw_id INTEGER
);

CREATE TABLE IF NOT EXISTS posts (
  post_id TEXT PRIMARY KEY,
  author_id TEXT, author_username TEXT,
  created_at TEXT,
  text TEXT,
  kind TEXT,                          -- original | quote | reply | repost
  in_reply_to_user_id TEXT,
  quoted_post_id TEXT, quoted_text TEXT, quoted_author_id TEXT, quoted_author_username TEXT,
  quoted_created_at TEXT,
  media_json TEXT,                    -- [{media_key,type,url,preview_image_url,alt_text}]
  quoted_media_json TEXT,
  impressions INTEGER, likes INTEGER, reposts INTEGER, replies INTEGER, quotes INTEGER, bookmarks INTEGER,
  lang TEXT, conversation_id TEXT,
  captured_at TEXT, raw_id INTEGER,
  source TEXT                         -- collection | discovery | daily
);
CREATE INDEX IF NOT EXISTS posts_author ON posts(author_id, created_at);

CREATE TABLE IF NOT EXISTS candidates (
  user_id TEXT PRIMARY KEY,
  username TEXT,
  sources TEXT,                       -- ;-separated: sweep:<release_id> | quoted | mentioned | grok
  first_seen TEXT
);

CREATE TABLE IF NOT EXISTS pass1 (
  post_id TEXT, model TEXT, prompt_version TEXT,
  about_release INTEGER, reason TEXT, raw_id INTEGER, ts TEXT,
  PRIMARY KEY (post_id, model, prompt_version)
);

CREATE TABLE IF NOT EXISTS extractions (
  post_id TEXT, model TEXT, prompt_version TEXT, run TEXT,
  raw_id INTEGER, ts TEXT, n_claims INTEGER, n_rejected INTEGER,
  uncheckable_reason TEXT,            -- set when no checkable claim survives
  PRIMARY KEY (post_id, model, prompt_version, run)
);

CREATE TABLE IF NOT EXISTS claims (
  claim_id TEXT PRIMARY KEY,          -- <post_id>-<run>-<n>
  post_id TEXT, run TEXT, model TEXT, prompt_version TEXT,
  account TEXT, posted_at TEXT,
  family TEXT,                        -- timing | attribute | uncheckable
  lab TEXT, model_name TEXT,
  window_phrase TEXT,                 -- 'unstated' if the post states none
  attribute TEXT, attribute_value TEXT,
  hedge TEXT,                         -- flat | hedged | question | joke
  origin TEXT,                        -- original | relay
  relayed_account TEXT,
  evidence TEXT,
  uncheckable_reason TEXT,
  claim_span TEXT,
  fields_json TEXT,                   -- full extracted object with spans
  valid INTEGER, rejection TEXT
);

CREATE TABLE IF NOT EXISTS alias_matches (
  name_key TEXT, lab TEXT, release_ids TEXT, method TEXT, reason TEXT, raw_id INTEGER,
  PRIMARY KEY (name_key, lab)
);

CREATE TABLE IF NOT EXISTS verdicts (
  claim_id TEXT, variant TEXT,        -- variant: main | soon7 | soon14 | soon30
  verdict TEXT,                       -- correct | incorrect | partial | open | uncheckable
  release_id TEXT, window_start TEXT, window_end TEXT,
  evidence_url TEXT, reason TEXT,
  signal_before_post INTEGER, hours_post_to_first_signal REAL, hours_post_to_release REAL,
  claimed_tier TEXT, window_days REAL,
  PRIMARY KEY (claim_id, variant)
);

CREATE TABLE IF NOT EXISTS deletion_checks (
  post_id TEXT, check_day INTEGER, checked_at TEXT, exists_now INTEGER, detail TEXT, raw_id INTEGER,
  PRIMARY KEY (post_id, check_day)
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


DERIVED_TABLES = ["users", "posts", "candidates", "pass1", "extractions", "claims",
                  "alias_matches", "verdicts", "deletion_checks"]
