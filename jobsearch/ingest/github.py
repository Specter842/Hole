"""Import public repositories as projects.

Unlike LinkedIn, GitHub's REST API is public, documented, and meant to be read
by tools -- no export file, no ToS conflict, no scraping. A username goes in,
`projects` rows come out, each carrying real evidence for the skill it used:
a repo's primary language is not a claim, it's a fact GitHub itself computed
by inspecting the code.

Forks are skipped by default. A fork proves you *ran* something, not that you
*built* it, and this tool exists to keep resume evidence honest about which is
which.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field as dc_field
from typing import Any

import requests

from .. import db

API_ROOT = "https://api.github.com"
USER_AGENT = "jobsearch-personal-tool/0.2 (+individual job seeker; public API only)"
REQUEST_TIMEOUT = 20


@dataclass
class GithubReport:
    source_id: int
    username: str
    created: dict[str, int] = dc_field(default_factory=dict)
    skipped_forks: list[str] = dc_field(default_factory=list)

    def bump(self, key: str, n: int = 1) -> None:
        self.created[key] = self.created.get(key, 0) + n

    def total(self) -> int:
        return sum(self.created.values())


def _get(path: str) -> Any:
    response = requests.get(
        f"{API_ROOT}{path}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code == 404:
        raise ValueError(f"no such GitHub user or resource: {path}")
    if response.status_code == 403:
        raise ValueError("GitHub API rate limit hit -- unauthenticated requests are capped at 60/hour")
    response.raise_for_status()
    return response.json()


def import_profile(
    conn: sqlite3.Connection,
    username: str,
    *,
    include_forks: bool = False,
    verified: int = 1,
) -> GithubReport:
    """Pull a user's public repos in as projects, with language as skill evidence.

    `verified=1` by default -- unlike a model's guess at what a document says,
    "this repo exists, is public, and GitHub says its language is X" is not an
    inference. It is what LinkedIn's own skill import wishes it had: evidence.
    """
    profile = _get(f"/users/{username}")
    source_id = db.insert_row(
        conn,
        "sources",
        {
            "kind": "github",
            "location": f"https://github.com/{username}",
            "label": profile.get("name") or username,
            "imported_at": db.now(),
            "notes": profile.get("bio"),
        },
    )
    report = GithubReport(source_id=source_id, username=username)

    repos = _get(f"/users/{username}/repos?per_page=100&sort=updated")
    for repo in repos:
        if repo.get("fork") and not include_forks:
            report.skipped_forks.append(repo["name"])
            continue

        project_id = db.insert_row(
            conn,
            "projects",
            {
                "name": repo["name"],
                "description": repo.get("description"),
                "url": repo.get("homepage") or repo.get("html_url"),
                "field": "software engineering",
                "source_id": source_id,
                "verified": verified,
            },
        )
        report.bump("projects")

        language = repo.get("language")
        if language:
            skill_id = db.upsert_skill(
                conn, language, category="language", source_id=source_id, verified=verified
            )
            if skill_id is not None:
                conn.execute(
                    "INSERT INTO skill_evidence (skill_id, project_id, note) VALUES (?, ?, ?)",
                    (skill_id, project_id, f"primary language of {repo['name']}, per GitHub"),
                )
                report.bump("skill_evidence")

        for topic in repo.get("topics") or []:
            skill_id = db.upsert_skill(
                conn, topic, category="topic", source_id=source_id, verified=verified
            )
            if skill_id is not None:
                conn.execute(
                    "INSERT INTO skill_evidence (skill_id, project_id, note) VALUES (?, ?, ?)",
                    (skill_id, project_id, f"topic tag on {repo['name']}, per GitHub"),
                )
                report.bump("skill_evidence")

    conn.commit()
    return report
