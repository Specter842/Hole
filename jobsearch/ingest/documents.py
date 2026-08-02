"""Extract career history from arbitrary documents.

A resume, an old performance review, a project write-up, a page of notes -- text
goes in, structured graph rows come out. A model does the extraction, so unlike
the LinkedIn importer these rows land **unverified**: they show up in
`profile review` until a human confirms them, and `tailor --verified-only` will
ignore them entirely.

The extraction prompt is as strict as the generation prompt. Nothing may be
inferred, normalised, or improved -- if a date or a metric is not written in the
document, the field comes back null.
"""

from __future__ import annotations

import json
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any

from .. import db, generate

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".yaml", ".yml", ".html"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | {".pdf", ".docx"}

MAX_DOCUMENT_CHARS = 60_000

EXTRACTION_SYSTEM_PROMPT = """You extract career history from a document into JSON.

You are building a factual database, not writing a resume. Accuracy beats completeness.

Hard rules:
- Extract only what the document states. Never infer, expand, or improve anything.
- If a date, employer, metric, or title is not written in the document, use null.
- Never convert a vague statement into a specific one. "Improved performance" stays
  "Improved performance"; it does not become "improved performance 40%".
- Copy quantified results verbatim into `quantified_impact` when the document gives them.
- Do not merge two roles into one, and do not split one role into two.
- Skills: list only technologies, tools, and named competencies the document actually
  mentions. Do not add adjacent or implied ones.

Return a single JSON object, no prose, no markdown fence:

{
  "profile": {"full_name": null, "headline": null, "summary": null, "email": null,
              "phone": null, "location": null, "website": null, "github": null},
  "experiences": [
    {"title": "", "organization": "", "employment_type": null, "location": null,
     "start_date": null, "end_date": null, "is_current": false, "description": null,
     "field": null, "skills": [],
     "accomplishments": [
       {"title": "", "description": "", "quantified_impact": null, "skills": []}
     ]}
  ],
  "education": [
    {"organization": "", "degree": null, "field_of_study": null, "start_date": null,
     "end_date": null, "grade": null, "activities": null}
  ],
  "projects": [
    {"name": "", "description": null, "role": null, "url": null, "start_date": null,
     "end_date": null, "skills": [],
     "accomplishments": [{"title": "", "description": "", "quantified_impact": null}]}
  ],
  "certifications": [
    {"name": "", "issuer": null, "issue_date": null, "expiry_date": null, "url": null}
  ],
  "awards": [{"name": "", "issuer": null, "date": null, "description": null}],
  "publications": [{"title": "", "publisher": null, "date": null, "url": null,
                    "description": null}],
  "skills": [],
  "notes": "anything you saw that did not fit the shape above"
}

Dates: use YYYY-MM or YYYY-MM-DD when the document gives a month; YYYY when it only
gives a year; null when it gives nothing. Omit sections that are absent -- an empty
array is correct, an invented entry is not.
"""


@dataclass
class DocumentReport:
    source_id: int
    path: str
    created: dict[str, int] = dc_field(default_factory=dict)
    notes: str = ""
    usage: dict[str, Any] = dc_field(default_factory=dict)
    warnings: list[str] = dc_field(default_factory=list)

    def bump(self, key: str, n: int = 1) -> None:
        self.created[key] = self.created.get(key, 0) + n

    def total(self) -> int:
        return sum(self.created.values())


# --------------------------------------------------------------------------- text extraction


def _docx_text(path: Path) -> str:
    """Pull paragraph text out of a .docx without a third-party dependency."""
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(path) as archive:
        try:
            xml = archive.read("word/document.xml")
        except KeyError as exc:
            raise ValueError(f"{path.name} is not a Word document") from exc
    root = ET.fromstring(xml)
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{namespace}p"):
        runs = [node.text or "" for node in paragraph.iter(f"{namespace}t")]
        line = "".join(runs).strip()
        if line:
            paragraphs.append(line)
    return "\n".join(paragraphs)


def _pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError(
            "Reading PDFs needs pypdf. Run: pip install pypdf\n"
            "(or convert the file to .docx / .txt and import that instead)"
        ) from exc
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_text(path: str | Path) -> str:
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        raise FileNotFoundError(f"No such file: {file_path}")
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        text = _pdf_text(file_path)
    elif suffix == ".docx":
        text = _docx_text(file_path)
    elif suffix in TEXT_SUFFIXES or suffix == "":
        text = file_path.read_text(encoding="utf-8", errors="replace")
    else:
        raise ValueError(
            f"Don't know how to read {suffix or 'this file'}. "
            f"Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )
    text = text.replace("\r\n", "\n").strip()
    if not text:
        raise ValueError(f"{file_path.name} contained no extractable text (scanned image?)")
    return text


# --------------------------------------------------------------------------- extraction


def parse_json_response(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("The model did not return JSON")
    return json.loads(text[start : end + 1])


def extract_entities(
    text: str,
    *,
    hint: str | None = None,
    model: str = generate.DEFAULT_MODEL,
    max_tokens: int = 8000,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(text) > MAX_DOCUMENT_CHARS:
        text = text[:MAX_DOCUMENT_CHARS]
    message = f"Document:\n{text}"
    if hint:
        message = f"Context about this document: {hint}\n\n{message}"
    raw, usage = generate.call_model(
        EXTRACTION_SYSTEM_PROMPT, message, model=model, max_tokens=max_tokens
    )
    return parse_json_response(raw), usage


# --------------------------------------------------------------------------- merge


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean_skills(value: Any) -> list[str]:
    return [str(s).strip() for s in _as_list(value) if str(s).strip()]


def merge_entities(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    source_id: int,
    report: DocumentReport,
    *,
    verified: int = 0,
    fill_profile: bool = True,
) -> None:
    """Write extracted entities into the graph. Profile fields never overwrite."""
    profile = payload.get("profile") or {}
    if fill_profile and isinstance(profile, dict):
        existing = db.get_profile(conn)
        for key, value in profile.items():
            if not value or not str(value).strip():
                continue
            canonical = db.PROFILE_ALIASES.get(str(key).lower(), str(key).lower())
            if existing.get(canonical):
                continue  # a later document does not get to rewrite your name
            db.set_profile_field(conn, canonical, str(value))
            report.bump("profile_fields")

    for entry in _as_list(payload.get("experiences")):
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "").strip()
        organization = str(entry.get("organization") or "").strip()
        if not title and not organization:
            continue
        experience_id = db.insert_row(
            conn,
            "experiences",
            {
                "organization_id": db.upsert_organization(conn, organization, kind="company"),
                "title": title or "Position",
                "employment_type": entry.get("employment_type"),
                "location": entry.get("location"),
                "start_date": entry.get("start_date"),
                "end_date": entry.get("end_date"),
                "is_current": 1 if entry.get("is_current") else 0,
                "description": entry.get("description"),
                "field": entry.get("field"),
                "source_id": source_id,
                "verified": verified,
            },
        )
        report.bump("experiences")
        db.link_skills_to(
            conn, _clean_skills(entry.get("skills")), "experience", experience_id,
            source_id=source_id, verified=verified,
        )

        for bullet in _as_list(entry.get("accomplishments")):
            if not isinstance(bullet, dict):
                continue
            description = str(bullet.get("description") or bullet.get("title") or "").strip()
            if not description:
                continue
            achievement_id = db.insert_row(
                conn,
                "achievements",
                {
                    "experience_id": experience_id,
                    "title": str(bullet.get("title") or description)[:120],
                    "description": description,
                    "quantified_impact": bullet.get("quantified_impact"),
                    "source_id": source_id,
                    "verified": verified,
                },
            )
            report.bump("accomplishments")
            db.link_skills_to(
                conn, _clean_skills(bullet.get("skills")), "achievement", achievement_id,
                source_id=source_id, verified=verified,
            )

    for entry in _as_list(payload.get("education")):
        if not isinstance(entry, dict):
            continue
        if not (entry.get("organization") or entry.get("degree")):
            continue
        db.insert_row(
            conn,
            "education",
            {
                "organization_id": db.upsert_organization(
                    conn, str(entry.get("organization") or ""), kind="school"
                ),
                "degree": entry.get("degree"),
                "field_of_study": entry.get("field_of_study"),
                "start_date": entry.get("start_date"),
                "end_date": entry.get("end_date"),
                "grade": entry.get("grade"),
                "activities": entry.get("activities"),
                "source_id": source_id,
                "verified": verified,
            },
        )
        report.bump("education")

    for entry in _as_list(payload.get("projects")):
        if not isinstance(entry, dict) or not str(entry.get("name") or "").strip():
            continue
        project_id = db.insert_row(
            conn,
            "projects",
            {
                "name": str(entry["name"]).strip(),
                "description": entry.get("description"),
                "role": entry.get("role"),
                "url": entry.get("url"),
                "start_date": entry.get("start_date"),
                "end_date": entry.get("end_date"),
                "source_id": source_id,
                "verified": verified,
            },
        )
        report.bump("projects")
        db.link_skills_to(
            conn, _clean_skills(entry.get("skills")), "project", project_id,
            source_id=source_id, verified=verified,
        )
        for bullet in _as_list(entry.get("accomplishments")):
            if not isinstance(bullet, dict):
                continue
            description = str(bullet.get("description") or bullet.get("title") or "").strip()
            if description:
                db.insert_row(
                    conn,
                    "achievements",
                    {
                        "project_id": project_id,
                        "title": str(bullet.get("title") or description)[:120],
                        "description": description,
                        "quantified_impact": bullet.get("quantified_impact"),
                        "source_id": source_id,
                        "verified": verified,
                    },
                )
                report.bump("accomplishments")

    for entry in _as_list(payload.get("certifications")):
        if isinstance(entry, dict) and str(entry.get("name") or "").strip():
            db.insert_row(
                conn,
                "certifications",
                {
                    "name": str(entry["name"]).strip(),
                    "issuer": entry.get("issuer"),
                    "issue_date": entry.get("issue_date"),
                    "expiry_date": entry.get("expiry_date"),
                    "url": entry.get("url"),
                    "source_id": source_id,
                    "verified": verified,
                },
            )
            report.bump("certifications")

    for entry in _as_list(payload.get("awards")):
        if isinstance(entry, dict) and str(entry.get("name") or "").strip():
            db.insert_row(
                conn,
                "awards",
                {
                    "name": str(entry["name"]).strip(),
                    "issuer": entry.get("issuer"),
                    "date": entry.get("date"),
                    "description": entry.get("description"),
                    "source_id": source_id,
                    "verified": verified,
                },
            )
            report.bump("awards")

    for entry in _as_list(payload.get("publications")):
        if isinstance(entry, dict) and str(entry.get("title") or "").strip():
            db.insert_row(
                conn,
                "publications",
                {
                    "title": str(entry["title"]).strip(),
                    "publisher": entry.get("publisher"),
                    "date": entry.get("date"),
                    "url": entry.get("url"),
                    "description": entry.get("description"),
                    "source_id": source_id,
                    "verified": verified,
                },
            )
            report.bump("publications")

    for name in _clean_skills(payload.get("skills")):
        if db.upsert_skill(conn, name, source_id=source_id, verified=verified) is not None:
            report.bump("skills")

    notes = payload.get("notes")
    if notes and str(notes).strip():
        report.notes = str(notes).strip()


def import_document(
    conn: sqlite3.Connection,
    path: str | Path,
    *,
    hint: str | None = None,
    model: str = generate.DEFAULT_MODEL,
    verified: int = 0,
) -> DocumentReport:
    file_path = Path(path).expanduser()
    text = extract_text(file_path)
    payload, usage = extract_entities(text, hint=hint, model=model)

    source_id = db.create_source(
        conn, "document", location=str(file_path), label=file_path.name, notes=hint
    )
    report = DocumentReport(source_id=source_id, path=str(file_path), usage=usage)
    merge_entities(conn, payload, source_id, report, verified=verified)

    if usage.get("stop_reason") == "max_tokens":
        report.warnings.append(
            "Extraction hit the token ceiling; the tail of this document may be missing."
        )
    if not report.total():
        report.warnings.append("Nothing extractable was found in this document.")
    return report
