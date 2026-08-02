"""Job sourcing: config in, `Posting` objects out.

Only ToS-safe endpoints live here. There is no Indeed connector (no public read
API, scraping blocked) and no LinkedIn connector (automated access banned). Both
omissions are deliberate and neither should be added.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .. import db
from ..config import Config
from . import aggregators, ats_boards
from .base import Posting, SourceError, SourceResult, dedupe, html_to_text  # noqa: F401

__all__ = [
    "Posting",
    "SourceError",
    "SourceResult",
    "SourcingReport",
    "collect",
    "store",
    "dedupe",
    "html_to_text",
]


@dataclass
class SourcingReport:
    postings: list[Posting] = field(default_factory=list)
    per_source: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def absorb(self, result: SourceResult) -> None:
        self.postings.extend(result.postings)
        self.per_source[result.source] = self.per_source.get(result.source, 0) + len(result.postings)
        self.errors.extend(result.errors)


def collect(config: Config) -> SourcingReport:
    """Run every enabled connector. A failing source never stops the others."""
    report = SourcingReport()
    search = config.search
    keyword_query = " ".join(search.titles[:3] or search.keywords[:3])
    location_query = search.locations[0] if search.locations else ""

    for source in config.enabled_sources():
        try:
            if source.name == "greenhouse":
                report.absorb(ats_boards.fetch_greenhouse(source.list_of("boards")))
            elif source.name == "lever":
                report.absorb(ats_boards.fetch_lever(source.list_of("companies")))
            elif source.name == "ashby":
                report.absorb(ats_boards.fetch_ashby(source.list_of("boards")))
            elif source.name == "adzuna":
                report.absorb(
                    aggregators.fetch_adzuna(
                        app_id=str(source.get("app_id", "")),
                        app_key=str(source.get("app_key", "")),
                        country=str(source.get("country", "us")),
                        what=keyword_query,
                        where=location_query,
                        results_per_page=int(source.get("results_per_page", 50)),
                        max_pages=int(source.get("max_pages", 2)),
                        max_age_days=search.max_age_days,
                    )
                )
            elif source.name == "usajobs":
                report.absorb(
                    aggregators.fetch_usajobs(
                        email=str(source.get("email", "")),
                        api_key=str(source.get("api_key", "")),
                        keyword=keyword_query,
                        location=location_query,
                        results_per_page=int(source.get("results_per_page", 50)),
                    )
                )
            else:
                report.errors.append(f"Unknown source '{source.name}' in config -- ignored.")
        except Exception as exc:  # a broken connector must not end the run
            report.errors.append(f"{source.name}: {type(exc).__name__}: {exc}")

    report.postings = dedupe(report.postings)
    return report


def store(conn: sqlite3.Connection, postings: list[Posting]) -> tuple[int, int]:
    """Insert new postings, ignoring ones already seen. Returns (new, duplicates)."""
    discovered_at = db.now()
    new = 0
    duplicates = 0
    for posting in postings:
        try:
            db.insert_row(conn, "jobs", posting.to_row(discovered_at))
            new += 1
        except sqlite3.IntegrityError:
            duplicates += 1
    return new, duplicates


def list_jobs(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    limit: int | None = None,
    order: str = "IFNULL(fit_score, -1) DESC, id DESC",
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM jobs"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += f" ORDER BY {order}"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return db.rows_to_dicts(conn.execute(sql, params))
