"""The views. Each returns a full HTML page.

These read the same tables the CLI reads, through the same `db` helpers, so the
two front ends can never drift into disagreeing about what is in the database.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .. import answers as answer_bank, db, graph as graph_module, llm, policy
from ..config import Config
from . import assets, charts, geo
from .html import esc, layout, notice, stat

STATUS_TONE = {
    "sent": "good",
    "approved": "good",
    "responded": "good",
    "drafted": "",
    "queued": "warn",
    "rejected": "bad",
    "failed": "bad",
    "skipped": "",
    "new": "",
    "scored": "",
    "tailored": "warn",
    "applied": "good",
}


def _tone(status: str | None) -> str:
    return STATUS_TONE.get((status or "").lower(), "")


def _job_title(job: dict[str, Any]) -> str:
    return f"{job.get('title') or 'Untitled'} @ {job.get('company') or 'Unknown'}"


# --------------------------------------------------------------------------- react pages
#
# Reach and Funnel are rendered by frontend/ (React, port of
# estics-reach-dashboard.jsx) instead of the server-side html.py/charts.py
# combination every other page uses. This function builds that page as a
# standalone document -- it does not call `layout()`, because these two pages
# own their own chrome (a left-nav sidebar), the way the reference does.
#
# Every figure passed in `data` is either a query already run for `/terminal`
# or a small variant of one (see the `_by_source`/`_funnel`/etc. helpers
# below) -- nothing here is invented or hardcoded.


def _react_page(title: str, route: str, data: dict[str, Any]) -> str:
    if not assets.REACT_BUNDLE_AVAILABLE:
        body = (
            f"<h1>{esc(title)}</h1>"
            + notice(
                "The React bundle has not been built.",
                [
                    "Run `npm install && npm run build` in frontend/, then reload this page.",
                ],
                tone="warn",
            )
        )
        return layout(title, body, active=f"/{route}")

    payload = esc(json.dumps(data, separators=(",", ":")))
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)} - Hole</title>"
        f"<style>{assets.REACT_BUNDLE_CSS}</style></head><body>"
        f'<div id="jobsearch-react-root" data-route="{esc(route)}" data-payload="{payload}"></div>'
        f"<script>{assets.REACT_BUNDLE_JS}</script></body></html>"
    )


# --------------------------------------------------------------------------- dashboard


def _config_notices(config: Config) -> list[dict[str, Any]]:
    """The config-problem / autonomous-mode warnings, as structured data.

    Honesty first: say plainly what is not wired up, because the most
    expensive failure here is believing the pipeline will send when it
    cannot. This is the same logic the old server-rendered dashboard led
    with -- kept intact and just reshaped for the React page to render.
    """
    notices: list[dict[str, Any]] = []
    problems = config.problems()
    if problems:
        notices.append({"tone": "bad", "text": "Not ready to run:", "items": list(problems)})

    if config.exists() and not config.autonomous:
        notices.append({
            "tone": "warn",
            "text": "Review-only mode. The pipeline will source, score, tailor, and "
            "verify, then stop. Nothing is sent.",
            "items": [],
        })
    elif config.autonomous:
        channels = [
            name
            for name, on in (
                ("email", config.dispatch.email.enabled),
                ("ats_form", config.dispatch.ats.enabled),
            )
            if on
        ]
        if channels:
            notices.append({
                "tone": "bad",
                "text": f"Autonomous mode is ON. Applications that pass every check are "
                f"sent via {', '.join(channels)} without asking.",
                "items": [],
            })
        else:
            notices.append({
                "tone": "warn",
                "text": "autonomous = true but no dispatch channel is enabled, so nothing "
                "can actually be sent. Everything will queue for review.",
                "items": [],
            })
    return notices


def dashboard(conn: sqlite3.Connection, config: Config) -> str:
    """The home page: the same reach/activity treatment `/reach` renders,
    populated with this app's actual dashboard-relevant data -- profile
    counts, job/application status, pipeline health -- rather than reach's
    figures. The config-problem and autonomous-mode notices the old
    server-rendered version led with are carried over unchanged (see
    `_config_notices`); dropping them silently would be a regression.
    """
    counts = db.profile_counts(conn)
    evidenced = len(db.skill_evidence_counts(conn))
    unevidenced = len(db.unevidenced_skills(conn))

    job_rows = conn.execute(
        "SELECT status, COUNT(*) n FROM jobs GROUP BY status"
    ).fetchall()
    jobs_by_status = {r["status"]: r["n"] for r in job_rows}
    app_rows = conn.execute(
        "SELECT status, COUNT(*) n FROM applications GROUP BY status"
    ).fetchall()
    apps_by_status = {r["status"]: r["n"] for r in app_rows}

    last = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    last_run = db.row_to_dict(last) if last else None

    postings_by_country = _postings_by_country(conn)
    applications_by_country = _applications_by_country(conn)
    country_pins = _country_pins(postings_by_country)
    remote, onsite = _remote_split(conn)
    src_rows, band_cols, fit_cells = _fit_by_source(conn)
    fit_grid = [
        [fit_cells.get((source, band), 0.0) for band in band_cols]
        for source in src_rows
    ]
    sent_vs_discovered = _sent_vs_discovered(conn)

    data = {
        "nav": _nav_counts(conn),
        "notices": _config_notices(config),
        "stats": [
            {"label": "positions", "value": counts.get("experiences", 0)},
            {"label": "accomplishments", "value": counts.get("achievements", 0)},
            {"label": "skills with evidence", "value": f"{evidenced}/{evidenced + unevidenced}"},
            {"label": "jobs sourced", "value": sum(jobs_by_status.values())},
            {"label": "awaiting review", "value": apps_by_status.get("drafted", 0)},
            {"label": "sent", "value": apps_by_status.get("sent", 0)},
        ],
        "jobs_by_status": [
            [status, n, _tone(status)] for status, n in sorted(jobs_by_status.items())
        ],
        "apps_by_status": [
            [status, n, _tone(status)] for status, n in sorted(apps_by_status.items())
        ],
        "model": llm.describe(),
        "last_run": (
            {
                "started_at": last_run.get("started_at"),
                "mode": last_run.get("mode"),
                "finished_at": last_run.get("finished_at"),
            }
            if last_run
            else None
        ),
        "postings_by_country": postings_by_country,
        "applications_by_country": applications_by_country,
        "country_pins": country_pins,
        "by_source": _by_source(conn),
        "by_location": _by_location(conn),
        "sent_vs_discovered": sent_vs_discovered,
        "remote": remote,
        "onsite": onsite,
        "fit_by_source": {"rows": src_rows, "cols": band_cols, "grid": fit_grid},
    }
    return _react_page("Dashboard", "", data)


# --------------------------------------------------------------------------- jobs


def jobs_list(conn: sqlite3.Connection, *, status: str | None = None) -> str:
    sql = "SELECT * FROM jobs"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY (fit_score IS NULL), fit_score DESC, id DESC LIMIT 400"
    rows = db.rows_to_dicts(conn.execute(sql, params).fetchall())

    data = {
        "nav": _nav_counts(conn),
        "page": "jobs_list",
        "status": status,
        "statuses": ["new", "scored", "tailored", "applied", "skipped", "failed"],
        "jobs": [
            {
                "id": job["id"],
                "title": job.get("title") or "Untitled",
                "company": job.get("company"),
                "location": job.get("location"),
                "remote": bool(job.get("remote")),
                "status": job.get("status") or "new",
                "tone": _tone(job.get("status")),
                "source": job.get("source"),
                "fit_score": job.get("fit_score"),
                "skip_reason": job.get("skip_reason"),
            }
            for job in rows
        ],
    }
    return _react_page("Jobs", "jobs", data)


def job_detail(conn: sqlite3.Connection, job_id: int, config: Config, token: str) -> str | None:
    job = db.get_row(conn, "jobs", job_id)
    if not job:
        return None

    existing = db.rows_to_dicts(
        conn.execute("SELECT * FROM applications WHERE job_id = ? ORDER BY id DESC", (job_id,)).fetchall()
    )

    data = {
        "nav": _nav_counts(conn),
        "page": "job_detail",
        "token": token,
        "job": {
            "id": job_id,
            "title": job.get("title") or "Untitled",
            "company": job.get("company") or "Unknown",
            "url": job.get("url"),
            "apply_url": job.get("apply_url"),
            "fit_score": job.get("fit_score"),
            "status": job.get("status") or "new",
            "tone": _tone(job.get("status")),
            "source": job.get("source"),
            "location": job.get("location"),
            "compensation": job.get("compensation"),
            "posted_at": job.get("posted_at"),
            "discovered_at": job.get("discovered_at"),
            "skip_reason": job.get("skip_reason"),
            "description": job.get("description") or "",
        },
        "applications": [
            {
                "id": a["id"],
                "status": a.get("status") or "",
                "tone": _tone(a.get("status")),
                "grounding_status": a.get("grounding_status") or "?",
                "grounding_clean": a.get("grounding_status") == "clean",
                "date": a.get("approved_at") or a.get("sent_date") or "",
            }
            for a in existing
        ],
    }
    return _react_page(_job_title(job), "jobs", data)


# --------------------------------------------------------------------------- queue


def queue(conn: sqlite3.Connection) -> str:
    rows = db.list_applications(conn)
    data = {
        "nav": _nav_counts(conn),
        "page": "queue",
        "applications": [
            {
                "id": a["id"],
                "role": a.get("role"),
                "company": a.get("company"),
                "fit_score": a.get("fit_score"),
                "grounding_status": a.get("grounding_status") or "?",
                "grounding_clean": a.get("grounding_status") == "clean",
                "status": a.get("status") or "",
                "tone": _tone(a.get("status")),
                "channel": a.get("channel"),
            }
            for a in rows
        ],
    }
    return _react_page("Queue", "queue", data)


def _read_bundle(resume_version: str | None) -> dict[str, str]:
    """Load the generated documents off disk, if the bundle still exists."""
    if not resume_version:
        return {}
    folder = Path(resume_version)
    if not folder.is_absolute():
        # `resume_version` holds a bare bundle name, and bundles are written to
        # <project>/output/<name> -- which is what every other reader assumes.
        # Resolving it against the project root instead pointed one directory
        # too high, so the UI reported documents missing that were on disk.
        folder = db.PROJECT_ROOT / "output" / folder
    out: dict[str, str] = {}
    for name in ("resume.md", "cover_letter.md", "fit_notes.md"):
        path = folder / name
        try:
            out[name] = path.read_text(encoding="utf-8")
        except OSError:
            continue
    return out


def application_detail(conn: sqlite3.Connection, app_id: int, token: str) -> str | None:
    app = db.get_application(conn, app_id)
    if not app:
        return None

    title = f"{app.get('role') or 'Application'} @ {app.get('company') or ''}".strip()

    reasons: list[str] = []
    raw_reasons = app.get("decision_reasons")
    if raw_reasons:
        try:
            parsed = json.loads(raw_reasons)
            reasons = [str(r) for r in parsed] if isinstance(parsed, list) else [str(parsed)]
        except (ValueError, TypeError):
            reasons = [str(raw_reasons)]

    documents = _read_bundle(app.get("resume_version"))

    data = {
        "nav": _nav_counts(conn),
        "page": "application_detail",
        "token": token,
        "application": {
            "id": app_id,
            "role": app.get("role"),
            "company": app.get("company"),
            "status": app.get("status") or "",
            "tone": _tone(app.get("status")),
            "fit_score": app.get("fit_score"),
            "grounding_status": app.get("grounding_status") or "unknown",
            "grounding_clean": app.get("grounding_status") == "clean",
            "channel": app.get("channel"),
            "source": app.get("source"),
            "job_url": app.get("job_url"),
            "resume_version": app.get("resume_version"),
            "approved_at": app.get("approved_at"),
            "sent_date": app.get("sent_date"),
            "dispatch_error": app.get("dispatch_error"),
        },
        "reasons": reasons,
        "documents": documents,
        "documents_missing": not documents,
    }
    return _react_page(title or "Application", "queue", data)


# --------------------------------------------------------------------------- profile


def profile(conn: sqlite3.Connection) -> str:
    g = graph_module.ProfileGraph.load(conn)
    counts = db.profile_counts(conn)
    evidence = db.skill_evidence_counts(conn)
    unevidenced = db.unevidenced_skills(conn)

    positions = [
        {
            "label": node.label,
            "dates": node.dates,
            "achievements": [
                {
                    "text": a.row.get("description") or a.title,
                    "impact": a.row.get("quantified_impact"),
                    "verified": bool(a.verified),
                }
                for a in node.achievements
            ],
        }
        for node in g.experiences
    ]
    projects = [
        {"name": node.row.get("name"), "description": node.row.get("description")}
        for node in g.projects
    ]
    skills = [
        {
            "name": skill.get("name"),
            "category": skill.get("category"),
            "evidence_count": evidence.get(skill["id"], 0),
        }
        for skill in db.list_skills(conn)
    ]

    data = {
        "nav": _nav_counts(conn),
        "page": "profile",
        "empty": not g.experiences and not g.projects,
        "counts": {
            key: counts.get(key, 0)
            for key in ("experiences", "achievements", "projects", "education", "skills")
        },
        "positions": positions,
        "projects": projects,
        "skills": skills,
        "unevidenced": [s["name"] for s in unevidenced],
    }
    return _react_page("Profile", "profile", data)


# --------------------------------------------------------------------------- review


REVIEWABLE = (
    "experiences",
    "achievements",
    "projects",
    "education",
    "certifications",
    "awards",
    "publications",
    "skills",
)


def review(conn: sqlite3.Connection, token: str) -> str:
    sections: list[dict[str, Any]] = []
    for name in REVIEWABLE:
        try:
            rows = db.rows_to_dicts(
                conn.execute(
                    f"SELECT * FROM {name} WHERE verified = 0 ORDER BY id"  # noqa: S608 - fixed allowlist
                ).fetchall()
            )
        except sqlite3.OperationalError:
            continue
        if not rows:
            continue
        sections.append({
            "name": name,
            "rows": [
                {
                    "id": row["id"],
                    "label": (
                        row.get("title")
                        or row.get("name")
                        or row.get("description")
                        or row.get("degree")
                        or "(no label)"
                    ),
                }
                for row in rows
            ],
        })
    data = {
        "nav": _nav_counts(conn),
        "page": "review",
        "token": token,
        "sections": sections,
    }
    return _react_page("Review", "", data)


# --------------------------------------------------------------------------- runs


def runs(conn: sqlite3.Connection) -> str:
    rows = db.rows_to_dicts(
        conn.execute("SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 100").fetchall()
    )
    data = {
        "nav": _nav_counts(conn),
        "page": "runs",
        "runs": [
            {
                "id": r["id"],
                "mode": r.get("mode") or "",
                "started_at": r.get("started_at"),
                "finished_at": r.get("finished_at"),
                "summary": r.get("summary") or r.get("notes") or "",
            }
            for r in rows
        ],
    }
    return _react_page("Runs", "runs", data)


# --------------------------------------------------------------------------- competitions

COMPETITION_CATEGORIES = (
    ("hackathon", "Hackathon"),
    ("case_competition", "Case Competition"),
    ("finance_competition", "Finance Competition"),
    ("other", "Other"),
)


def competitions_page(conn: sqlite3.Connection, token: str) -> str:
    """Hackathons, case competitions, finance competitions, newest first.

    Two kinds of row share this table. A hand-entered one records something
    already done and carries `result`. One found by `sourcing.competitions`
    records something still open and carries `deadline`/`tracks`/`apply_url`
    instead -- `status` is what separates them."""
    rows = db.rows_to_dicts(
        conn.execute("SELECT * FROM competitions ORDER BY id DESC").fetchall()
    )
    data = {
        "nav": _nav_counts(conn),
        "page": "competitions",
        "token": token,
        "categories": [{"value": v, "label": lbl} for v, lbl in COMPETITION_CATEGORIES],
        "competitions": [
            {
                "id": r["id"],
                "name": r.get("name"),
                "category": r.get("category"),
                "result": r.get("result"),
                "period": r.get("period"),
                "description": r.get("description"),
                "tech": r.get("tech"),
                "url": r.get("url"),
                "deadline": r.get("deadline"),
                "team_size": r.get("team_size"),
                "tracks": r.get("tracks"),
                "apply_url": r.get("apply_url"),
                "status": r.get("status") or "entered",
                "discovery_source": r.get("discovery_source"),
            }
            for r in rows
        ],
    }
    return _react_page("Competitions", "competitions", data)


# --------------------------------------------------------------------------- answers

# The questions almost every application form asks. Offered as prompts with the
# answers left blank -- seeding actual values would be inventing facts about the
# candidate, which is the one thing this whole system exists not to do.
COMMON_QUESTIONS = (
    ("authorized to work", "Are you authorized to work in this country?", "Yes / No"),
    ("visa sponsorship", "Do you now or will you require sponsorship?", "Yes / No"),
    ("notice period", "What is your notice period?", "e.g. Two weeks"),
    ("start date", "When can you start?", "e.g. Two weeks from offer"),
    ("years of experience", "Years of relevant experience", "e.g. 8"),
    ("how did you hear", "How did you hear about us?", "e.g. Company website"),
    ("linkedin", "LinkedIn profile", "https://linkedin.com/in/..."),
    ("relocate", "Are you willing to relocate?", "Yes / No"),
    ("remote", "Are you comfortable working remotely?", "Yes"),
    ("what city", "Which city are you based in?", "City, State, Country"),
)


def answers_page(conn: sqlite3.Connection, token: str) -> str:
    """The answer bank: what forms fill from, and what is still missing.

    Gaps come first. They are the questions that actually stopped an application,
    counted, so the most expensive blank sits at the top.
    """
    stored = answer_bank.list_all(conn)
    gaps = answer_bank.gaps(conn)
    known = {a.pattern for a in stored}
    suggestions = [q for q in COMMON_QUESTIONS if q[0] not in known]

    data = {
        "nav": _nav_counts(conn),
        "page": "answers",
        "token": token,
        "gaps": [
            {
                "question": str(gap.get("question") or ""),
                "company": gap.get("company"),
                "seen_count": int(gap.get("seen_count") or 1),
            }
            for gap in gaps
        ],
        "stored": [
            {"id": item.id, "pattern": item.pattern, "answer": item.answer, "company": item.company}
            for item in stored
        ],
        "suggestions": [
            {"pattern": pattern, "label": label, "hint": hint}
            for pattern, label, hint in suggestions
        ],
    }
    return _react_page("Answers", "answers", data)


# --------------------------------------------------------------------------- profile editor

PROFILE_FIELDS = (
    ("full_name", "Full name", "text", "As it should appear on applications."),
    ("email", "Email", "email", ""),
    ("phone", "Phone", "tel", "Include country code if applying internationally."),
    ("location", "Location", "text", "City, State, Country."),
    ("headline", "Headline", "text", "e.g. Senior Backend Engineer."),
    ("linkedin_url", "LinkedIn", "url", ""),
    ("github", "GitHub", "url", ""),
    ("website", "Website / portfolio", "url", ""),
    (
        "work_authorization", "Work authorization", "text",
        "e.g. US citizen, or Requires H-1B sponsorship.",
    ),
)


def profile_edit(conn: sqlite3.Connection, token: str) -> str:
    """Every field a form might ask for, in one place.

    These are the values typed straight into applications, so this page is the
    difference between a form that completes and one that stops halfway.
    """
    current = db.get_profile(conn)
    known = {name for name, _label, _kind, _hint in PROFILE_FIELDS}
    extra = {
        key: value
        for key, value in current.items()
        if key not in known and key not in ("updated_at", "summary")
    }
    missing = [label for name, label, _k, _h in PROFILE_FIELDS if not current.get(name)]

    data = {
        "nav": _nav_counts(conn),
        "page": "profile_edit",
        "token": token,
        "fields": [
            {"name": name, "label": label, "kind": kind, "hint": hint, "value": current.get(name, "")}
            for name, label, kind, hint in PROFILE_FIELDS
        ],
        "summary": current.get("summary", ""),
        "missing": missing,
        "extra": [{"key": key, "value": value} for key, value in sorted(extra.items())],
    }
    return _react_page("Your details", "profile", data)


# --------------------------------------------------------------------------- profile builder


def _dates(start: Any, end: Any, current: Any = 0) -> str:
    """A plain-text date range -- no HTML entities. This value travels inside
    the JSON payload React parses and renders directly (React escapes on its
    own), not into a hand-built HTML string, so pre-escaping it here would
    show up as literal "&ndash;" text instead of an en dash.
    """
    start = str(start) if start else "?"
    if current and not end:
        return f"{start} – present"
    return f"{start} – {str(end) if end else 'present'}"


def profile_build(conn: sqlite3.Connection, token: str) -> str:
    """Enter your history here; resumes are generated from it.

    Laid out the way the graph is actually shaped: accomplishments sit under the
    position they happened at, because that is the constraint the schema
    enforces and the reason a generated resume can place a bullet under the
    right employer without the model guessing.
    """
    graph = graph_module.ProfileGraph.load(conn)
    counts = graph.counts()
    unevidenced = db.unevidenced_skills(conn)

    positions = []
    for node in graph.experiences:
        record = node.row
        achievements = []
        for achievement in node.achievements:
            impact = achievement.row.get("quantified_impact")
            title = str(achievement.row.get("title") or "")
            detail = str(achievement.row.get("description") or "")
            # Imports often store a truncated title alongside the full sentence
            # it was cut from, and printing both reads as a stutter. Show the
            # detail only when it says something the title does not.
            if detail.startswith(title[:40]) and len(title) >= 40:
                title, detail = detail, ""
            elif detail == title:
                detail = ""
            achievements.append({
                "id": achievement.row.get("id"),
                "title": title,
                "detail": detail,
                "impact": impact,
            })
        positions.append({
            "id": record.get("id"),
            "title": record.get("title"),
            "organization": record.get("organization"),
            "dates": _dates(record.get("start_date"), record.get("end_date"), record.get("is_current")),
            "location": record.get("location"),
            "achievements": achievements,
        })

    education = [
        {
            "id": record.get("id"),
            "degree": record.get("degree"),
            "organization": record.get("organization"),
            "field_of_study": record.get("field_of_study"),
            "dates": _dates(record.get("start_date"), record.get("end_date")),
        }
        for record in db.list_education(conn)
    ]

    projects = [
        {"id": node.row.get("id"), "name": node.row.get("name"), "description": node.row.get("description")}
        for node in graph.projects
    ]

    certifications = [
        {
            "id": record.get("id"),
            "name": record.get("name"),
            "issuer": record.get("issuer"),
            "issue_date": record.get("issue_date"),
        }
        for record in db.rows_to_dicts(
            conn.execute("SELECT * FROM certifications ORDER BY IFNULL(issue_date, '') DESC")
        )
    ]

    evidenced_skills = [
        {"name": s.get("name"), "evidence_count": s.get("evidence_count", 0)}
        for s in graph.evidenced_skills[:80]
    ]

    data = {
        "nav": _nav_counts(conn),
        "page": "profile_build",
        "token": token,
        "empty": not graph.experiences,
        "counts": counts,
        "positions": positions,
        "education": education,
        "projects": projects,
        "certifications": certifications,
        "evidenced_skills": evidenced_skills,
        "unevidenced_skills": [str(s.get("name")) for s in unevidenced[:40]],
    }
    return _react_page("Your history", "profile", data)


# --------------------------------------------------------------------------- terminal


def _fit_histogram(conn: sqlite3.Connection) -> list[tuple[str, float]]:
    """Scored jobs bucketed by fit, ten points wide."""
    rows = conn.execute(
        "SELECT CAST(fit_score / 10 AS INTEGER) AS bucket, COUNT(*) AS n "
        "FROM jobs WHERE fit_score IS NOT NULL GROUP BY bucket ORDER BY bucket"
    ).fetchall()
    counts = {int(r["bucket"]): int(r["n"]) for r in rows}
    return [(f"{low}", float(counts.get(low // 10, 0))) for low in range(0, 100, 10)]


def _by_source(conn: sqlite3.Connection) -> list[tuple[str, float]]:
    rows = conn.execute(
        "SELECT source, COUNT(*) AS n FROM jobs GROUP BY source ORDER BY n DESC LIMIT 10"
    ).fetchall()
    return [(str(r["source"]), float(r["n"])) for r in rows]


def _by_location(conn: sqlite3.Connection, *, limit: int = 8) -> list[tuple[str, float]]:
    """Top raw location strings, most-listed first.

    Not normalized -- a Greenhouse posting open to three cities reports all
    three in one string, and collapsing that into "one location" would claim a
    precision the posting itself does not have.
    """
    rows = conn.execute(
        "SELECT location, COUNT(*) AS n FROM jobs "
        "WHERE location IS NOT NULL AND location != '' "
        "GROUP BY location ORDER BY n DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [(str(r["location"])[:46], float(r["n"])) for r in rows]


def _remote_split(conn: sqlite3.Connection) -> tuple[float, float]:
    row = conn.execute(
        "SELECT SUM(remote) AS remote, COUNT(*) AS total FROM jobs"
    ).fetchone()
    remote = float(row["remote"] or 0)
    total = float(row["total"] or 0)
    return remote, total - remote


def _fit_by_source(
    conn: sqlite3.Connection, *, top_sources: int = 5
) -> tuple[list[str], list[str], dict[tuple[str, str], float]]:
    """Fit-score density per source: which boards actually match this profile.

    Bands run in fixed order (0-10 first) rather than by count, because a
    heatmap's columns are an axis, not a ranking -- reordering them by size
    would make the grid unreadable as a distribution.
    """
    sources = [
        str(r["source"])
        for r in conn.execute(
            "SELECT source, COUNT(*) n FROM jobs GROUP BY source ORDER BY n DESC LIMIT ?",
            (top_sources,),
        )
    ]
    bands = [f"{low}" for low in range(0, 100, 10)]
    cells: dict[tuple[str, str], float] = {}
    if sources:
        placeholders = ",".join("?" * len(sources))
        rows = conn.execute(
            f"SELECT source, CAST(fit_score / 10 AS INTEGER) AS band, COUNT(*) AS n "
            f"FROM jobs WHERE fit_score IS NOT NULL AND source IN ({placeholders}) "
            "GROUP BY source, band",
            sources,
        ).fetchall()
        for r in rows:
            band_low = min(int(r["band"]), 9) * 10
            cells[(str(r["source"]), f"{band_low}")] = float(r["n"])
    return sources, bands, cells


def _discovery(conn: sqlite3.Connection) -> list[tuple[str, float]]:
    rows = conn.execute(
        "SELECT substr(discovered_at, 1, 10) AS day, COUNT(*) AS n "
        "FROM jobs WHERE discovered_at IS NOT NULL "
        "GROUP BY day ORDER BY day DESC LIMIT 30"
    ).fetchall()
    return [(str(r["day"])[5:], float(r["n"])) for r in reversed(rows)]


def _nav_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Small counts the nav shell needs everywhere (e.g. a real badge on the
    Queue item), so every `_react_page` call can carry the same shape."""
    queued = conn.execute(
        "SELECT COUNT(*) n FROM applications WHERE status = 'drafted'"
    ).fetchone()["n"]
    return {"queued": int(queued)}


def _country_pins(rows: list[tuple[str, float]], *, limit: int = 8) -> list[dict[str, Any]]:
    """Turn `_postings_by_country`-shaped rows into map pins with a real
    projected position, using `geo.COUNTRY_CENTROIDS`. A country this app's
    data names but that has no centroid entry is skipped rather than guessed
    at -- see `geo.py` for why the centroid table is deliberately small.
    """
    pins = []
    for name, value in rows[:limit]:
        centroid = geo.COUNTRY_CENTROIDS.get(name)
        if not centroid:
            continue
        top, left = geo.project_equirect(*centroid)
        pins.append(
            {
                "name": name,
                "value": value,
                "flag": geo.flag_emoji(name),
                "top": round(top, 2),
                "left": round(left, 2),
            }
        )
    return pins


def _sent_vs_discovered(conn: sqlite3.Connection, *, days: int = 14) -> dict[str, Any]:
    """Two genuinely distinct real series over the same day buckets: postings
    discovered and applications sent, so the two-series bar chart in the
    reference layout has real second series rather than an invented one."""
    disc_rows = conn.execute(
        "SELECT substr(discovered_at, 1, 10) AS day, COUNT(*) AS n "
        "FROM jobs WHERE discovered_at IS NOT NULL "
        "GROUP BY day ORDER BY day DESC LIMIT ?",
        (days,),
    ).fetchall()
    sent_rows = conn.execute(
        "SELECT substr(sent_date, 1, 10) AS day, COUNT(*) AS n "
        "FROM applications WHERE sent_date IS NOT NULL "
        "GROUP BY day ORDER BY day DESC LIMIT ?",
        (days,),
    ).fetchall()
    discovered = {str(r["day"]): float(r["n"]) for r in disc_rows}
    sent = {str(r["day"]): float(r["n"]) for r in sent_rows}
    days_seen = sorted(set(discovered) | set(sent))
    return {
        "days": [d[5:] for d in days_seen],
        "discovered": [discovered.get(d, 0.0) for d in days_seen],
        "sent": [sent.get(d, 0.0) for d in days_seen],
    }


def _week_over_week_delta(conn: sqlite3.Connection) -> float | None:
    """Percent change in postings discovered, last 7 full days vs the 7
    before that. Returns None (never a fabricated number) when there isn't
    enough history to compare two full weeks."""
    rows = conn.execute(
        "SELECT substr(discovered_at, 1, 10) AS day, COUNT(*) AS n "
        "FROM jobs WHERE discovered_at IS NOT NULL GROUP BY day ORDER BY day DESC"
    ).fetchall()
    if len(rows) < 14:
        return None
    counts = [float(r["n"]) for r in rows]
    last7 = sum(counts[0:7])
    prev7 = sum(counts[7:14])
    if prev7 == 0:
        return None
    return round((last7 - prev7) / prev7 * 100.0, 2)


def _postings_by_country(conn: sqlite3.Connection) -> list[tuple[str, float]]:
    """Real country counts, from postings' own location text.

    A posting only counts toward a country when that country's name actually
    appears in its location string (`geo.extract_countries`) -- "Remote" alone,
    or an unrecognized city, counts toward none. A compound posting like
    "Remote (US/UK)" counts toward both, because it genuinely reaches both.
    """
    counts: dict[str, float] = {}
    rows = conn.execute(
        "SELECT location FROM jobs WHERE location IS NOT NULL AND location != ''"
    )
    for row in rows:
        for country in geo.extract_countries(row["location"]):
            counts[country] = counts.get(country, 0.0) + 1.0
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def _applications_by_country(conn: sqlite3.Connection) -> list[tuple[str, float]]:
    """Same idea, but for where applications actually went -- joined through to
    the job's own location rather than duplicating it onto `applications`."""
    counts: dict[str, float] = {}
    rows = conn.execute(
        "SELECT jobs.location AS location FROM applications "
        "JOIN jobs ON jobs.id = applications.job_id "
        "WHERE jobs.location IS NOT NULL AND jobs.location != ''"
    )
    for row in rows:
        for country in geo.extract_countries(row["location"]):
            counts[country] = counts.get(country, 0.0) + 1.0
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def reach(conn: sqlite3.Connection) -> str:
    """Where postings come from and where applications go. Every figure here
    is one already computed for `/terminal`, or a small extension of the same
    queries (see `_postings_by_country`/`_applications_by_country`).
    """
    total = conn.execute("SELECT COUNT(*) n FROM jobs").fetchone()["n"]
    sources = len(conn.execute("SELECT DISTINCT source FROM jobs").fetchall())
    sent = conn.execute(
        "SELECT COUNT(*) n FROM applications WHERE status = 'sent'"
    ).fetchone()["n"]
    remote, onsite = _remote_split(conn)
    by_source = _by_source(conn)
    by_location = _by_location(conn)
    src_rows, band_cols, fit_cells = _fit_by_source(conn)
    discovery = _discovery(conn)
    postings_by_country = _postings_by_country(conn)
    applications_by_country = _applications_by_country(conn)
    country_pins = _country_pins(postings_by_country)
    sent_vs_discovered = _sent_vs_discovered(conn)
    delta = _week_over_week_delta(conn)

    grid = [
        [fit_cells.get((source, band), 0.0) for band in band_cols]
        for source in src_rows
    ]

    data = {
        "nav": _nav_counts(conn),
        "stats": [
            {
                "label": "postings sourced",
                "value": f"{total:,}",
                **({"delta": delta} if delta is not None else {}),
            },
            {"label": "remote postings", "value": f"{int(remote):,}"},
            {"label": "boards tracked", "value": f"{sources:,}"},
            {"label": "applications sent", "value": f"{sent:,}"},
        ],
        "by_source": by_source,
        "by_location": by_location,
        "postings_by_country": postings_by_country,
        "applications_by_country": applications_by_country,
        "country_pins": country_pins,
        "sent_vs_discovered": sent_vs_discovered,
        "discovery": discovery,
        "remote": remote,
        "onsite": onsite,
        "fit_by_source": {"rows": src_rows, "cols": band_cols, "grid": grid},
    }
    return _react_page("Reach", "reach", data)


def _funnel(conn: sqlite3.Connection) -> list[tuple[str, float]]:
    """Where postings stop. Each stage counts everything that reached it."""
    total = conn.execute("SELECT COUNT(*) n FROM jobs").fetchone()["n"]
    scored = conn.execute(
        "SELECT COUNT(*) n FROM jobs WHERE fit_score IS NOT NULL"
    ).fetchone()["n"]
    drafted = conn.execute("SELECT COUNT(*) n FROM applications").fetchone()["n"]
    approved = conn.execute(
        "SELECT COUNT(*) n FROM applications WHERE status IN ('approved','sent')"
    ).fetchone()["n"]
    sent = conn.execute(
        "SELECT COUNT(*) n FROM applications WHERE status = 'sent'"
    ).fetchone()["n"]
    return [
        ("sourced", float(total)),
        ("scored", float(scored)),
        ("tailored", float(drafted)),
        ("approved", float(approved)),
        ("sent", float(sent)),
    ]


def _top_skills(conn: sqlite3.Connection) -> list[tuple[str, float]]:
    """Skills with the most evidence behind them.

    `skill_evidence_counts` is keyed by skill id, not name, so this joins back
    to `skills` -- labelling the bars with row ids reads as nonsense.
    """
    rows = conn.execute(
        "SELECT s.name AS name, COUNT(*) AS n FROM skill_evidence e "
        "JOIN skills s ON s.id = e.skill_id "
        "GROUP BY s.id ORDER BY n DESC, s.name LIMIT 8"
    ).fetchall()
    return [(str(r["name"]), float(r["n"])) for r in rows]


def funnel(conn: sqlite3.Connection) -> str:
    """Where postings stop, and whether your profile can even claim the
    skills a role wants. Same queries `/terminal` already runs (`_funnel`,
    `_fit_histogram`, `_top_skills`, the evidenced/unevidenced skill counts);
    nothing here is computed twice with different logic that could quietly
    drift from what `/terminal` shows.
    """
    stages = _funnel(conn)
    fit_histogram = _fit_histogram(conn)
    evidenced = len(db.skill_evidence_counts(conn))
    unevidenced = len(db.unevidenced_skills(conn))
    top_skills = _top_skills(conn)

    data = {
        "nav": _nav_counts(conn),
        "stages": stages,
        "fit_histogram": fit_histogram,
        "evidenced": evidenced,
        "unevidenced": unevidenced,
        "top_skills": top_skills,
    }
    return _react_page("Funnel", "funnel", data)


def terminal(conn: sqlite3.Connection) -> str:
    """The numbers, as pictures.

    Every panel is a single-series magnitude or trend, which is why there is one
    colour in most of them -- the height already carries the value, and shading
    it as well would spend the only free channel on information the chart has
    shown twice.
    """
    scored = conn.execute(
        "SELECT COUNT(*) n, AVG(fit_score) avg, MAX(fit_score) best "
        "FROM jobs WHERE fit_score IS NOT NULL"
    ).fetchone()
    total = conn.execute("SELECT COUNT(*) n FROM jobs").fetchone()["n"]
    evidenced = len(db.skill_evidence_counts(conn))
    unevidenced = len(db.unevidenced_skills(conn))

    body = "<h1>Terminal</h1>"
    body += (
        '<p class="sub">Every number on this page is counted from the database, '
        "not estimated.</p>"
    )

    # The one figure the view leads with.
    best = scored["best"] if scored and scored["best"] is not None else 0
    body += (
        '<div class="hero">'
        f'<div class="hero-n">{esc(f"{best:.0f}")}</div>'
        '<div class="hero-k">best fit score on record</div>'
        "</div>"
    )

    average = scored["avg"] if scored and scored["avg"] is not None else 0
    body += '<div class="grid">'
    body += stat(f"{total:,}", "jobs sourced")
    body += stat(f"{int(scored['n']):,}" if scored else "0", "scored")
    body += stat(f"{average:.1f}", "mean fit")
    body += stat(f"{evidenced}/{evidenced + unevidenced}", "skills evidenced")
    body += "</div>"

    body += '<h2 class="rise">Fit score distribution</h2>'
    body += (
        '<p class="muted">Where your matches actually cluster. A tall left side '
        "means the boards are feeding you the wrong roles.</p>"
    )
    body += charts.column_chart(_fit_histogram(conn), title="Jobs per 10-point band")

    body += '<h2 class="rise">Pipeline</h2>'
    body += (
        '<p class="muted">Counts at each stage. The gap between two bars is where '
        "postings are being dropped.</p>"
    )
    body += charts.bar_chart(_funnel(conn), title="Postings reaching each stage")

    body += '<h2 class="rise">Reach</h2>'
    body += (
        '<p class="muted">Where postings actually come from, and where they say '
        "the work is.</p>"
    )
    body += '<div class="row2">'
    body += (
        '<div class="panel rise">'
        + charts.bubble_cluster(_by_source(conn), title="Source reach")
        + "</div>"
    )
    body += (
        '<div class="panel rise">'
        + charts.ranked_list(_by_location(conn), title="Top locations", unit="")
        + "</div>"
    )
    body += "</div>"

    body += '<h2 class="rise">Activity</h2>'
    remote, onsite = _remote_split(conn)
    src_rows, band_cols, fit_cells = _fit_by_source(conn)
    body += '<div class="row3">'
    body += (
        '<div class="panel rise">'
        + charts.line_chart(_discovery(conn), title="Jobs first seen, by day")
        + "</div>"
    )
    body += (
        '<div class="panel rise">'
        + charts.donut_chart("remote", remote, "onsite", onsite, title="Remote vs onsite")
        + "</div>"
    )
    body += (
        '<div class="panel rise">'
        + charts.heatmap_chart(
            src_rows, band_cols, fit_cells,
            title="Fit score by source", row_title="Source", col_title="Fit band",
        )
        + "</div>"
    )
    body += "</div>"

    body += '<h2 class="rise">Skills</h2>'
    body += (
        '<p class="muted">An unevidenced skill never reaches a resume, so the red '
        "share is the part of your profile that cannot be used yet.</p>"
    )
    body += charts.split_bar(
        "evidenced", evidenced, "unevidenced", unevidenced,
        title="Claimable vs unusable",
    )
    if _top_skills(conn):
        body += charts.bar_chart(_top_skills(conn), title="Most-evidenced skills")

    return layout("Terminal", body, active="/terminal")
