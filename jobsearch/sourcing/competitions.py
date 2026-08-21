"""Finding competitions to enter, the same way `sourcing/` finds jobs to apply to.

The Competitions page was manual entry only: you saw a hackathon somewhere, you
typed it in. This module is the other half -- it goes and looks, so the row
appears before the deadline rather than after it.

Same rules as the job connectors next door: documented public endpoints only,
no scraping a site that forbids it, and a dead source is skipped rather than
fatal. Notably absent for that reason:

- Unstop     requires cookies and blocks non-browser clients outright.
- Devfolio   listings are client-rendered; the HTML a fetch returns is empty.
- LinkedIn   User Agreement bans automated access.

For those, `discover` records the platform as a bookmark row instead, so the
dashboard still tells you where to go look by hand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from .base import SourceError, fetch_json

DEVPOST_API = "https://devpost.com/api/hackathons"

# Devpost theme names -> the category the Competitions page groups by. Anything
# unmapped stays a hackathon, which is what Devpost is mostly for.
FINANCE_THEMES = {"fintech", "finance", "blockchain", "cryptocurrency"}
CASE_THEMES = {"business", "entrepreneurship", "social good"}


@dataclass
class Opportunity:
    """One competition worth considering. Mirrors the `competitions` table."""

    name: str
    category: str = "hackathon"
    description: str | None = None
    url: str | None = None
    apply_url: str | None = None
    deadline: str | None = None
    period: str | None = None
    team_size: str | None = None
    tracks: list[str] = field(default_factory=list)
    prize: str | None = None
    source: str = ""

    def to_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "url": self.url,
            "apply_url": self.apply_url,
            "deadline": self.deadline,
            "period": self.period,
            "team_size": self.team_size,
            "tracks": ", ".join(self.tracks) or None,
            "discovery_source": self.source,
            "status": "discovered",
        }


def _strip_tags(value: str | None) -> str | None:
    """Devpost returns prize amounts wrapped in markup: "$<span ...>740,000</span>"."""
    if not value:
        return None
    return re.sub(r"<[^>]+>", "", value).strip() or None


def _category_for(themes: list[str]) -> str:
    lowered = {t.lower() for t in themes}
    if lowered & FINANCE_THEMES:
        return "finance_competition"
    if lowered & CASE_THEMES:
        return "case_competition"
    return "hackathon"


MONTH_RE = re.compile(
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*", re.IGNORECASE
)


def _deadline_from(period: str | None) -> str | None:
    """Devpost gives a range; the deadline is its end.

    Two shapes, and the second is why this is not a one-liner:
        "Jul 31 - Oct 01, 2026"   both halves name a month
        "Aug 01 - 31, 2026"       the end half does not, and reading it alone
                                  would produce a monthless "31, 2026"
    """
    if not period:
        return None
    head, _, tail = period.rpartition("-")
    tail = tail.strip()
    if not tail:
        return period.strip() or None
    if not MONTH_RE.search(tail):
        month = MONTH_RE.search(head)
        if month:
            tail = f"{month.group(0)} {tail}"
    return tail or None


def devpost(*, limit: int = 100, online_only: bool = False) -> Iterator[Opportunity]:
    """Open hackathons on Devpost. Public JSON API, no key required."""
    seen = 0
    for page in range(1, 12):  # hard stop; the API pages 9 at a time
        if seen >= limit:
            return
        try:
            payload = fetch_json(DEVPOST_API, params={"status[]": "open", "page": page})
        except SourceError:
            raise
        entries = payload.get("hackathons") or []
        if not entries:
            return
        for entry in entries:
            if seen >= limit:
                return
            location = (entry.get("displayed_location") or {}).get("location") or ""
            if online_only and "online" not in location.lower():
                continue
            themes = [t.get("name", "") for t in (entry.get("themes") or []) if t.get("name")]
            period = entry.get("submission_period_dates")
            prize = _strip_tags(entry.get("prize_amount"))
            bits = [b for b in (location, f"prize {prize}" if prize else None) if b]
            yield Opportunity(
                name=entry.get("title") or "untitled",
                category=_category_for(themes),
                description=" -- ".join(bits) or None,
                url=entry.get("url"),
                apply_url=entry.get("start_a_submission_url") or entry.get("url"),
                deadline=_deadline_from(period),
                period=period,
                tracks=themes,
                prize=prize,
                source="devpost",
            )
            seen += 1


# Platforms that cannot be read programmatically. Recorded as bookmark rows so
# the dashboard still points at them rather than silently omitting them.
MANUAL_PLATFORMS = (
    Opportunity(
        name="Unstop -- browse by hand",
        category="other",
        description="2,500+ India hackathons and case competitions. Blocks automated clients, so this is a bookmark, not a feed.",
        url="https://unstop.com/hackathons",
        source="manual",
    ),
    Opportunity(
        name="Devfolio -- browse by hand",
        category="other",
        description="India's main Web3/blockchain hackathon platform. Listings are client-rendered, so they cannot be fetched.",
        url="https://devfolio.co/hackathons/upcoming",
        source="manual",
    ),
    Opportunity(
        name="MLH -- browse by hand",
        category="other",
        description="200+ student hackathons per season, mostly remote-eligible.",
        url="https://mlh.com/events",
        source="manual",
    ),
)


def discover(*, limit: int = 100, online_only: bool = False,
             include_manual: bool = True) -> tuple[list[Opportunity], list[str]]:
    """Every connector, failures collected rather than raised."""
    found: list[Opportunity] = []
    errors: list[str] = []
    try:
        found.extend(devpost(limit=limit, online_only=online_only))
    except SourceError as exc:
        errors.append(f"devpost: {exc}")
    if include_manual:
        found.extend(MANUAL_PLATFORMS)
    return found, errors


def save(conn: Any, opportunities: list[Opportunity]) -> tuple[int, int]:
    """Insert what is new, leave what is already there alone.

    Dedup is on `name` because that is what a person recognises, and because a
    row typed in by hand should not be duplicated by the scraper finding the
    same event later. A hand-entered row keeps its own text -- discovery never
    overwrites something a person wrote.
    """
    existing = {
        (r["name"] or "").strip().lower()
        for r in conn.execute("SELECT name FROM competitions")
    }
    added = skipped = 0
    for opp in opportunities:
        if opp.name.strip().lower() in existing:
            skipped += 1
            continue
        row = opp.to_row()
        conn.execute(
            """INSERT INTO competitions
               (name, category, description, url, apply_url, deadline, period,
                team_size, tracks, discovery_source, status, discovered_at)
               VALUES (:name, :category, :description, :url, :apply_url, :deadline,
                       :period, :team_size, :tracks, :discovery_source, :status,
                       datetime('now'))""",
            row,
        )
        existing.add(opp.name.strip().lower())
        added += 1
    conn.commit()
    return added, skipped
