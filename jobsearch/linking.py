"""Attach skills to the records that prove them.

A skill imported from LinkedIn arrives naked: LinkedIn stores that you claim
"Kubernetes" but not where you used it. Rather than inventing a link, this scans
the text of real records for literal mentions and creates evidence only where the
skill is actually named. Everything it cannot link stays unevidenced and is
reported, so the gap is visible instead of silently filled.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from . import db

# Short names ("R", "Go", "C") match far too much text to be linked
# case-insensitively, so they are held to a stricter standard.
SHORT_NAME_LIMIT = 2


@dataclass
class Link:
    skill_id: int
    skill_name: str
    target_type: str
    target_id: int
    target_label: str

    def __str__(self) -> str:
        return f"{self.skill_name} -> {self.target_type} {self.target_id} ({self.target_label})"


def _mention_pattern(name: str) -> re.Pattern[str] | None:
    text = name.strip()
    if not text:
        return None
    escaped = re.escape(text).replace(r"\ ", r"\s+")
    flags = 0 if len(text) <= SHORT_NAME_LIMIT else re.IGNORECASE
    try:
        return re.compile(rf"(?<![\w+#]){escaped}(?![\w+#])", flags)
    except re.error:
        return None


def _record_text(*parts: Any) -> str:
    return " \n ".join(str(p) for p in parts if p)


def autolink_skills(conn: sqlite3.Connection, *, commit: bool = True) -> list[Link]:
    """Create skill_evidence rows wherever a skill is literally named in a record."""
    skills = [
        (int(r["id"]), str(r["name"]))
        for r in conn.execute("SELECT id, name FROM skills ORDER BY LENGTH(name) DESC")
    ]
    if not skills:
        return []

    targets: list[tuple[str, int, str, str]] = []  # (type, id, label, text)

    for row in db.list_experiences(conn):
        targets.append(
            (
                "experience",
                int(row["id"]),
                f"{row.get('title')} @ {row.get('organization')}",
                _record_text(row.get("title"), row.get("description"), row.get("field")),
            )
        )
    for row in db.list_projects(conn):
        targets.append(
            (
                "project",
                int(row["id"]),
                str(row.get("name")),
                _record_text(row.get("name"), row.get("description"), row.get("role")),
            )
        )
    for row in db.list_achievements(conn):
        targets.append(
            (
                "achievement",
                int(row["id"]),
                str(row.get("title")),
                _record_text(row.get("title"), row.get("description"), row.get("quantified_impact")),
            )
        )
    for row in db.list_education(conn):
        targets.append(
            (
                "education",
                int(row["id"]),
                str(row.get("degree") or row.get("organization")),
                _record_text(
                    row.get("degree"),
                    row.get("field_of_study"),
                    row.get("description"),
                    row.get("activities"),
                ),
            )
        )
    for row in db.list_table(conn, "certifications"):
        targets.append(
            (
                "certification",
                int(row["id"]),
                str(row.get("name")),
                _record_text(row.get("name"), row.get("issuer")),
            )
        )

    created: list[Link] = []
    for skill_id, skill_name in skills:
        pattern = _mention_pattern(skill_name)
        if pattern is None:
            continue
        for target_type, target_id, label, text in targets:
            if not text or not pattern.search(text):
                continue
            existing = conn.execute(
                f"SELECT 1 FROM skill_evidence WHERE skill_id = ? AND {target_type}_id = ?",
                (skill_id, target_id),
            ).fetchone()
            if existing:
                continue
            db.add_skill_evidence(
                conn, skill_id, target_type, target_id, note="auto: named in record text"
            )
            created.append(Link(skill_id, skill_name, target_type, target_id, label))

    if commit:
        conn.commit()
    return created
