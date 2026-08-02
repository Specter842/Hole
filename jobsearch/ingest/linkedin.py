"""Import a LinkedIn data export.

This is the archive LinkedIn emails you from Settings > Data Privacy > Get a copy
of your data. It is your own data, delivered by LinkedIn, so there is no scraping
and no automated access involved -- which is exactly why it is the route this
tool supports.

The parser is deliberately forgiving: LinkedIn has renamed these columns several
times and regional exports differ, so files are located by fuzzy name and columns
by a list of candidate headers.
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
import zipfile
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Iterable, Sequence

from .. import db

MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "sept": "09", "oct": "10", "nov": "11", "dec": "12",
}

BULLET_RE = re.compile(r"^\s*[•▪◦*\-•●·]\s+")


@dataclass
class ImportReport:
    source_id: int
    created: dict[str, int] = dc_field(default_factory=dict)
    skipped: list[str] = dc_field(default_factory=list)
    files_seen: list[str] = dc_field(default_factory=list)

    def bump(self, key: str, n: int = 1) -> None:
        self.created[key] = self.created.get(key, 0) + n

    def total(self) -> int:
        return sum(self.created.values())


def parse_linkedin_date(value: str | None) -> str | None:
    """'Mar 2023' -> '2023-03'; 'Jan 5, 2023' -> '2023-01-05'; '2023' -> '2023'."""
    if not value:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("present", "current", "-"):
        return None

    iso = re.match(r"^(\d{4})-(\d{2})(?:-(\d{2}))?$", text)
    if iso:
        return text

    day_month_year = re.match(r"^([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})$", text)
    if day_month_year:
        month = MONTHS.get(day_month_year.group(1)[:4].lower().rstrip(".")) or MONTHS.get(
            day_month_year.group(1)[:3].lower()
        )
        if month:
            return f"{day_month_year.group(3)}-{month}-{int(day_month_year.group(2)):02d}"

    month_year = re.match(r"^([A-Za-z]{3,9})\.?\s+(\d{4})$", text)
    if month_year:
        month = MONTHS.get(month_year.group(1)[:3].lower())
        if month:
            return f"{month_year.group(2)}-{month}"

    year_only = re.match(r"^(\d{4})$", text)
    if year_only:
        return text

    return text  # keep whatever it was rather than dropping a real date


def _normalize_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def pick(row: dict[str, str], *candidates: str) -> str | None:
    """Case- and punctuation-insensitive column lookup."""
    normalized = {_normalize_key(k): v for k, v in row.items()}
    for candidate in candidates:
        value = normalized.get(_normalize_key(candidate))
        if value and str(value).strip():
            return str(value).strip()
    return None


def split_bullets(text: str | None) -> list[str]:
    """Pull bullet lines out of a position description.

    Only splits when the text is actually formatted as a list -- prose stays
    whole, because chopping a paragraph into fake bullets would invent emphasis
    that was never there.
    """
    if not text:
        return []
    lines = [line.strip() for line in str(text).replace("\r\n", "\n").split("\n")]
    lines = [line for line in lines if line]
    marked = [line for line in lines if BULLET_RE.match(line)]
    if len(marked) >= 2:
        return [BULLET_RE.sub("", line).strip() for line in marked]
    if len(lines) >= 3 and all(len(line) < 400 for line in lines):
        # Newline-separated one-liners with no markers: still a list.
        return lines
    return []


# --------------------------------------------------------------------------- archive access


class Archive:
    """A LinkedIn export, either an unzipped folder or the .zip itself."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._zip: zipfile.ZipFile | None = None
        if path.is_file() and path.suffix.lower() == ".zip":
            self._zip = zipfile.ZipFile(path)

    def close(self) -> None:
        if self._zip:
            self._zip.close()

    def __enter__(self) -> "Archive":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def names(self) -> list[str]:
        if self._zip:
            return [n for n in self._zip.namelist() if n.lower().endswith(".csv")]
        return [str(p.relative_to(self.path)) for p in self.path.rglob("*.csv")]

    def read(self, name: str) -> str:
        if self._zip:
            return self._zip.read(name).decode("utf-8-sig", errors="replace")
        return (self.path / name).read_text(encoding="utf-8-sig", errors="replace")

    def find(self, *stems: str) -> str | None:
        """Locate a CSV by fuzzy stem, e.g. find('Positions') -> 'Positions.csv'."""
        wanted = [_normalize_key(s) for s in stems]
        for name in self.names():
            stem = _normalize_key(Path(name).stem)
            if any(stem == w or stem.startswith(w) or w in stem for w in wanted):
                return name
        return None

    def rows(self, *stems: str) -> list[dict[str, str]]:
        name = self.find(*stems)
        if not name:
            return []
        try:
            text = self.read(name)
        except (OSError, KeyError):
            return []
        # LinkedIn sometimes prefixes a "Notes:" preamble before the real header.
        lines = text.splitlines()
        start = 0
        for index, line in enumerate(lines[:8]):
            if line.count(",") >= 1 and not line.lower().startswith("notes"):
                start = index
                break
        reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
        return [dict(row) for row in reader if any((v or "").strip() for v in row.values())]


# --------------------------------------------------------------------------- import


def import_archive(
    conn: sqlite3.Connection,
    path: str | Path,
    *,
    verified: int = 1,
) -> ImportReport:
    """Load an export into the graph. Additive; never deletes existing rows."""
    archive_path = Path(path).expanduser()
    if not archive_path.exists():
        raise FileNotFoundError(f"No LinkedIn export at {archive_path}")

    source_id = db.create_source(
        conn, "linkedin_export", location=str(archive_path), label=archive_path.name
    )
    report = ImportReport(source_id=source_id)

    with Archive(archive_path) as archive:
        report.files_seen = sorted(Path(n).name for n in archive.names())
        _import_profile(conn, archive, report)
        _import_positions(conn, archive, source_id, report, verified)
        _import_education(conn, archive, source_id, report, verified)
        _import_projects(conn, archive, source_id, report, verified)
        _import_certifications(conn, archive, source_id, report, verified)
        _import_skills(conn, archive, source_id, report, verified)
        _import_simple(conn, archive, source_id, report, verified)

    if not report.total():
        report.skipped.append(
            "No recognizable LinkedIn CSVs found. Expected files such as Positions.csv, "
            "Education.csv, Skills.csv at the archive root."
        )
    return report


def _import_profile(conn: sqlite3.Connection, archive: Archive, report: ImportReport) -> None:
    rows = archive.rows("Profile")
    if rows:
        row = rows[0]
        first = pick(row, "First Name") or ""
        last = pick(row, "Last Name") or ""
        full_name = f"{first} {last}".strip()
        for key, value in (
            ("full_name", full_name),
            ("headline", pick(row, "Headline")),
            ("summary", pick(row, "Summary")),
            ("location", pick(row, "Geo Location", "Location", "Address")),
            ("website", pick(row, "Websites")),
        ):
            if value:
                db.set_profile_field(conn, key, value)
                report.bump("profile_fields")

    emails = archive.rows("Email Addresses", "Emails")
    primary = next(
        (r for r in emails if (pick(r, "Primary") or "").lower().startswith(("y", "t"))), None
    )
    chosen = primary or (emails[0] if emails else None)
    if chosen:
        address = pick(chosen, "Email Address", "Email")
        if address:
            db.set_profile_field(conn, "email", address)
            report.bump("profile_fields")

    phones = archive.rows("PhoneNumbers", "Phone Numbers")
    if phones:
        number = pick(phones[0], "Number", "Phone Number")
        if number:
            db.set_profile_field(conn, "phone", number)
            report.bump("profile_fields")


def _import_positions(
    conn: sqlite3.Connection,
    archive: Archive,
    source_id: int,
    report: ImportReport,
    verified: int,
) -> None:
    for row in archive.rows("Positions"):
        title = pick(row, "Title", "Position")
        company = pick(row, "Company Name", "Company")
        if not title and not company:
            continue
        end_date = parse_linkedin_date(pick(row, "Finished On", "End Date"))
        description = pick(row, "Description")
        org_id = db.upsert_organization(conn, company, kind="company")
        experience_id = db.insert_row(
            conn,
            "experiences",
            {
                "organization_id": org_id,
                "title": title or "Position",
                "location": pick(row, "Location"),
                "start_date": parse_linkedin_date(pick(row, "Started On", "Start Date")),
                "end_date": end_date,
                "is_current": 0 if end_date else 1,
                "description": description,
                "source_id": source_id,
                "verified": verified,
            },
        )
        report.bump("experiences")

        for bullet in split_bullets(description):
            db.insert_row(
                conn,
                "achievements",
                {
                    "experience_id": experience_id,
                    "title": bullet[:80],
                    "description": bullet,
                    "source_id": source_id,
                    "verified": verified,
                },
            )
            report.bump("accomplishments")


def _import_education(
    conn: sqlite3.Connection,
    archive: Archive,
    source_id: int,
    report: ImportReport,
    verified: int,
) -> None:
    for row in archive.rows("Education"):
        school = pick(row, "School Name", "School")
        degree = pick(row, "Degree Name", "Degree")
        if not school and not degree:
            continue
        db.insert_row(
            conn,
            "education",
            {
                "organization_id": db.upsert_organization(conn, school, kind="school"),
                "degree": degree,
                "field_of_study": pick(row, "Field Of Study", "Major"),
                "start_date": parse_linkedin_date(pick(row, "Start Date", "Started On")),
                "end_date": parse_linkedin_date(pick(row, "End Date", "Finished On")),
                "activities": pick(row, "Activities"),
                "description": pick(row, "Notes", "Description"),
                "source_id": source_id,
                "verified": verified,
            },
        )
        report.bump("education")


def _import_projects(
    conn: sqlite3.Connection,
    archive: Archive,
    source_id: int,
    report: ImportReport,
    verified: int,
) -> None:
    for row in archive.rows("Projects"):
        name = pick(row, "Title", "Name")
        if not name:
            continue
        db.insert_row(
            conn,
            "projects",
            {
                "name": name,
                "description": pick(row, "Description"),
                "url": pick(row, "Url", "URL"),
                "start_date": parse_linkedin_date(pick(row, "Started On", "Start Date")),
                "end_date": parse_linkedin_date(pick(row, "Finished On", "End Date")),
                "source_id": source_id,
                "verified": verified,
            },
        )
        report.bump("projects")


def _import_certifications(
    conn: sqlite3.Connection,
    archive: Archive,
    source_id: int,
    report: ImportReport,
    verified: int,
) -> None:
    for row in archive.rows("Certifications"):
        name = pick(row, "Name", "Title")
        if not name:
            continue
        db.insert_row(
            conn,
            "certifications",
            {
                "name": name,
                "issuer": pick(row, "Authority", "Issuer"),
                "issue_date": parse_linkedin_date(pick(row, "Started On", "Issue Date")),
                "expiry_date": parse_linkedin_date(pick(row, "Finished On", "Expiration Date")),
                "credential_id": pick(row, "License Number", "Credential ID"),
                "url": pick(row, "Url", "URL"),
                "source_id": source_id,
                "verified": verified,
            },
        )
        report.bump("certifications")


def _import_skills(
    conn: sqlite3.Connection,
    archive: Archive,
    source_id: int,
    report: ImportReport,
    verified: int,
) -> None:
    """Skills arrive with no evidence attached.

    LinkedIn does not say *where* a skill was used, and inventing that link would
    be exactly the kind of unsupported claim this tool exists to prevent. They
    land unevidenced; `link` matches them against real records afterwards.
    """
    for row in archive.rows("Skills"):
        name = pick(row, "Name", "Skill")
        if not name:
            continue
        if db.upsert_skill(conn, name, source_id=source_id, verified=verified) is not None:
            report.bump("skills")

    endorsements: dict[str, int] = {}
    for row in archive.rows("Endorsement_Received_Info", "Endorsements"):
        skill = pick(row, "Skill Name", "Skill")
        if skill:
            endorsements[db.normalize_skill(skill)] = endorsements.get(db.normalize_skill(skill), 0) + 1
    for normalized, count in endorsements.items():
        conn.execute(
            "UPDATE skills SET category = COALESCE(category, ?) WHERE normalized_name = ?",
            (f"endorsed x{count}", normalized),
        )


def _import_simple(
    conn: sqlite3.Connection,
    archive: Archive,
    source_id: int,
    report: ImportReport,
    verified: int,
) -> None:
    for row in archive.rows("Honors", "Awards"):
        name = pick(row, "Title", "Name")
        if name:
            db.insert_row(
                conn,
                "awards",
                {
                    "name": name,
                    "issuer": pick(row, "Issuer", "Authority"),
                    "date": parse_linkedin_date(pick(row, "Issued On", "Date")),
                    "description": pick(row, "Description"),
                    "source_id": source_id,
                    "verified": verified,
                },
            )
            report.bump("awards")

    for row in archive.rows("Publications"):
        title = pick(row, "Name", "Title")
        if title:
            db.insert_row(
                conn,
                "publications",
                {
                    "title": title,
                    "publisher": pick(row, "Publisher"),
                    "date": parse_linkedin_date(pick(row, "Published On", "Date")),
                    "url": pick(row, "Url", "URL"),
                    "description": pick(row, "Description"),
                    "source_id": source_id,
                    "verified": verified,
                },
            )
            report.bump("publications")

    for row in archive.rows("Languages"):
        name = pick(row, "Name", "Language")
        if name:
            try:
                db.insert_row(
                    conn,
                    "languages",
                    {
                        "name": name,
                        "proficiency": pick(row, "Proficiency"),
                        "source_id": source_id,
                        "verified": verified,
                    },
                )
                report.bump("languages")
            except sqlite3.IntegrityError:
                pass  # already known

    for row in archive.rows("Volunteering", "Volunteer Experience"):
        role = pick(row, "Role", "Title")
        company = pick(row, "Company Name", "Organization")
        if role or company:
            db.insert_row(
                conn,
                "volunteering",
                {
                    "organization_id": db.upsert_organization(conn, company, kind="nonprofit"),
                    "role": role,
                    "cause": pick(row, "Cause"),
                    "start_date": parse_linkedin_date(pick(row, "Started On", "Start Date")),
                    "end_date": parse_linkedin_date(pick(row, "Finished On", "End Date")),
                    "description": pick(row, "Description"),
                    "source_id": source_id,
                    "verified": verified,
                },
            )
            report.bump("volunteering")

    for row in archive.rows("Recommendations_Received", "Recommendations Received"):
        text = pick(row, "Text", "Recommendation")
        if not text:
            continue
        first = pick(row, "First Name") or ""
        last = pick(row, "Last Name") or ""
        db.insert_row(
            conn,
            "recommendations",
            {
                "author_name": f"{first} {last}".strip() or None,
                "author_title": pick(row, "Job Title", "Title"),
                "author_organization": pick(row, "Company"),
                "date": parse_linkedin_date(pick(row, "Creation Date", "Date")),
                "text": text,
                "source_id": source_id,
                "verified": verified,
            },
        )
        report.bump("recommendations")
