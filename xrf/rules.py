"""Deadline conventions from RULES.md section 3, as code. RULES.md is authoritative."""
from __future__ import annotations

import calendar
import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import config

RULES_TAG = "rules-v1"


@dataclass
class Window:
    start: datetime
    end: datetime
    lower: datetime | None = None          # releases before this are 'partial (early)'
    point: datetime | None = None          # named day / explicit date: +/-12h tolerance
    variants: dict[str, datetime] = field(default_factory=dict)   # soon7/soon14/soon30
    rule: str = ""

    @property
    def days(self) -> float:
        return (self.end - self.start).total_seconds() / 86400


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _end_of_day(d: datetime) -> datetime:
    return d.replace(hour=23, minute=59, second=59, microsecond=0)


def _end_of_week(t: datetime, plus_weeks: int = 0) -> datetime:
    sunday = t + timedelta(days=6 - t.weekday() + 7 * plus_weeks)
    return _end_of_day(sunday)


def _start_of_week(t: datetime, plus_weeks: int) -> datetime:
    monday = t - timedelta(days=t.weekday()) + timedelta(weeks=plus_weeks)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def _end_of_month(y: int, m: int) -> datetime:
    while m > 12:
        y, m = y + 1, m - 12
    return datetime(y, m, calendar.monthrange(y, m)[1], 23, 59, 59, tzinfo=timezone.utc)


MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9
WEEKDAYS = {d.lower(): i for i, d in enumerate(calendar.day_name)}
WEEKDAYS.update({d.lower(): i for i, d in enumerate(calendar.day_abbr)})
NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
       "eight": 8, "nine": 9, "ten": 10, "a couple of": 2, "couple": 2, "few": 3, "a few": 3}

# (regex, rule name). Order matters: first match wins. Listed phrases map per RULES.md section 3.
PHRASES: list[tuple[str, str]] = [
    (r"\b(today|tonight|later today|in a few hours|in (?:a couple of|\d+) hours|this (?:morning|afternoon|evening))\b", "today"),
    (r"\btomorrow\b", "tomorrow"),
    (r"\b(next week)\b", "next_week"),
    (r"\b(this weekend|over the weekend)\b", "this_week"),
    (r"\b(this week|later this week|end of (?:the )?week|by the weekend|within the week)\b", "this_week"),
    (r"\b(next month)\b", "next_month"),
    (r"\b(this month|later this month|end of (?:the |this )?month|by month'?s end|within the month)\b", "this_month"),
    (r"\b(in the coming weeks|coming weeks|next few weeks|in a few weeks|within weeks)\b", "coming_weeks"),
    (r"\b(imminent|imminently|any day now|very soon|any minute|any moment|momentarily|any hour now|super soon|very very soon)\b", "imminent"),
    (r"\b(end of (?:the )?year|by year'?s end|before the year ends|this year|by eoy|eoy|before 20\d\d)\b", "eoy"),
    (r"\b(q[1-4]|h[12])(?:\s*'?(\d{2,4}))?\b", "quarter"),
    (r"\bin (\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|a couple of|a few) (day|days|week|weeks)\b", "in_n"),
    (r"\b(soon|soonish|coming|shortly|around the corner|on the way|on its way|incoming)\b", "soon"),
]


def _explicit_date(p: str, post: datetime) -> datetime | None:
    m = re.search(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b", p)
    if m:
        mon, day = MONTHS[m.group(1)], int(m.group(2))
    else:
        m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b", p)
        if m:
            mon, day = MONTHS[m.group(2)], int(m.group(1))
        else:
            m = re.search(r"\b(\d{1,2})/(\d{1,2})\b", p)   # US m/d, as most cohort accounts write
            if not m:
                return None
            mon, day = int(m.group(1)), int(m.group(2))
    if not (1 <= mon <= 12 and 1 <= day <= 31):
        return None
    year = post.year
    try:
        d = datetime(year, mon, day, tzinfo=timezone.utc)
    except ValueError:
        return None
    if d < post - timedelta(days=60):    # "Jan 5" written in December means next year
        d = d.replace(year=year + 1)
    return d


def _weekday(p: str, post: datetime) -> datetime | None:
    m = re.search(r"\b(?:on |this |next )?(" + "|".join(sorted(WEEKDAYS, key=len, reverse=True)) + r")\b", p)
    if not m:
        return None
    target = WEEKDAYS[m.group(1)]
    delta = (target - post.weekday()) % 7
    if "next " + m.group(1) in p and delta < 7:
        delta += 7 if delta == 0 else 0
    return (post + timedelta(days=delta)).replace(hour=0, minute=0, second=0, microsecond=0)


def window_for(phrase: str | None, post: datetime) -> Window | str | None:
    """Return a Window, the string 'unstated', or None if the phrase is not mappable."""
    if phrase is None or phrase.strip().lower() in ("", "unstated", "none"):
        return "unstated"
    p = phrase.lower().strip()
    d = _explicit_date(p, post)
    if d is not None:
        return Window(post, d + timedelta(hours=35, minutes=59, seconds=59), point=d, rule="explicit_date")
    for rx, rule in PHRASES:
        m = re.search(rx, p)
        if not m:
            continue
        if rule == "today":
            return Window(post, post + timedelta(hours=24), rule=rule)
        if rule == "tomorrow":
            return Window(post, post + timedelta(hours=48), rule=rule)
        if rule == "this_week":
            return Window(post, _end_of_week(post), rule=rule)
        if rule == "next_week":
            return Window(post, _end_of_week(post, 1), lower=_start_of_week(post, 1), rule=rule)
        if rule == "this_month":
            return Window(post, _end_of_month(post.year, post.month), rule=rule)
        if rule == "next_month":
            return Window(post, _end_of_month(post.year, post.month + 1),
                          lower=_end_of_month(post.year, post.month) + timedelta(seconds=1), rule=rule)
        if rule == "coming_weeks":
            return Window(post, post + timedelta(days=30), rule=rule)
        if rule == "imminent":
            return Window(post, post + timedelta(days=7), rule=rule)
        if rule == "eoy":
            return Window(post, datetime(post.year, 12, 31, 23, 59, 59, tzinfo=timezone.utc), rule=rule)
        if rule == "quarter":
            q = m.group(1)
            yr = m.group(2)
            year = post.year if not yr else (int(yr) + 2000 if len(yr) == 2 else int(yr))
            end_month = {"q1": 3, "q2": 6, "q3": 9, "q4": 12, "h1": 6, "h2": 12}[q]
            return Window(post, _end_of_month(year, end_month), rule=rule)
        if rule == "in_n":
            n = int(m.group(1)) if m.group(1).isdigit() else NUM[m.group(1)]
            unit = 7 if m.group(2).startswith("week") else 1
            return Window(post, post + timedelta(days=n * unit + 1), rule=rule)
        if rule == "soon":
            v = {f"soon{k}": post + timedelta(days=k) for k in (7, 14, 30)}
            return Window(post, v["soon14"], variants=v, rule=rule)
    wd = _weekday(p, post)
    if wd is not None:
        return Window(post, wd + timedelta(hours=35, minutes=59, seconds=59), point=wd, rule="weekday")
    return None


# ---- rules-v1 tag guard -------------------------------------------------------------------------

def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def assert_rules_tagged() -> str:
    """Refuse to run resolution against untagged rules. RULES.md must equal the version frozen at the rules-v1
    tag: checked against the git tag when it exists, else against RULES.lock (committed with the tag; it holds the
    tag name and the SHA-256 of RULES.md at tagging). A later change is accepted only if DECISIONS.md has a dated
    entry recording 'RULES.md sha256 <first 12 hex>' of the new file."""
    cur = (config.ROOT / "RULES.md").read_bytes()
    frozen = None
    try:
        frozen = _sha(subprocess.run(["git", "-C", str(config.ROOT), "show", f"{RULES_TAG}:RULES.md"],
                                     capture_output=True, check=True).stdout)
    except (subprocess.CalledProcessError, FileNotFoundError):
        lock = config.ROOT / "RULES.lock"
        if lock.exists():
            for line in lock.read_text().splitlines():
                if line.startswith(RULES_TAG + " "):
                    frozen = line.split()[1]
    if frozen is None:
        raise RuntimeError(f"neither git tag {RULES_TAG} nor RULES.lock found: resolution refuses to run against untagged rules")
    if _sha(cur) == frozen:
        return RULES_TAG
    h = _sha(cur)[:12]
    decisions = (config.ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    if f"RULES.md sha256 {h}" in decisions:
        return f"{RULES_TAG}+{h}"
    raise RuntimeError(f"RULES.md differs from {RULES_TAG} and DECISIONS.md has no dated entry recording "
                       f"'RULES.md sha256 {h}'. Refusing to resolve.")
