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
from .html import (
    esc,
    field,
    form,
    form_button,
    kv,
    layout,
    notice,
    pill,
    score_bar,
    stat,
    table,
)

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


# --------------------------------------------------------------------------- dashboard


def dashboard(conn: sqlite3.Connection, config: Config) -> str:
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

    body = "<h1>Dashboard</h1>"

    # Honesty first: say plainly what is not wired up, because the most
    # expensive failure here is believing the pipeline will send when it cannot.
    problems = config.problems()
    if problems:
        body += notice("Not ready to run:", problems, tone="bad")

    if config.exists() and not config.autonomous:
        body += notice(
            "Review-only mode. The pipeline will source, score, tailor, and verify, "
            "then stop. Nothing is sent.",
            tone="warn",
        )
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
            body += notice(
                f"Autonomous mode is ON. Applications that pass every check are sent "
                f"via {', '.join(channels)} without asking.",
                tone="bad",
            )
        else:
            body += notice(
                "autonomous = true but no dispatch channel is enabled, so nothing can "
                "actually be sent. Everything will queue for review.",
                tone="warn",
            )

    body += '<div class="grid">'
    body += stat(counts.get("experiences", 0), "positions")
    body += stat(counts.get("achievements", 0), "accomplishments")
    body += stat(f"{evidenced}/{evidenced + unevidenced}", "skills with evidence")
    body += stat(sum(jobs_by_status.values()), "jobs sourced")
    body += stat(apps_by_status.get("drafted", 0), "awaiting review")
    body += stat(apps_by_status.get("sent", 0), "sent")
    body += "</div>"

    body += "<h2>Model</h2><div class='card'>"
    body += f"<span class='mono'>{esc(llm.describe())}</span></div>"

    if jobs_by_status:
        body += "<h2>Jobs by status</h2><div class='card'>"
        body += " ".join(
            pill(f"{status}: {n}", _tone(status)) for status, n in sorted(jobs_by_status.items())
        )
        body += "</div>"

    if apps_by_status:
        body += "<h2>Applications by status</h2><div class='card'>"
        body += " ".join(
            pill(f"{status}: {n}", _tone(status)) for status, n in sorted(apps_by_status.items())
        )
        body += "</div>"

    last = conn.execute(
        "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if last:
        row = db.row_to_dict(last) or {}
        body += "<h2>Last run</h2><div class='card'>" + kv(
            [
                ("Started", esc(row.get("started_at"))),
                ("Mode", esc(row.get("mode"))),
                ("Finished", esc(row.get("finished_at")) or "<span class='muted'>did not finish</span>"),
            ]
        ) + "</div>"

    return layout("Dashboard", body, active="/")


# --------------------------------------------------------------------------- jobs


def jobs_list(conn: sqlite3.Connection, *, status: str | None = None) -> str:
    sql = "SELECT * FROM jobs"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY (fit_score IS NULL), fit_score DESC, id DESC LIMIT 400"
    rows = db.rows_to_dicts(conn.execute(sql, params).fetchall())

    filters = " ".join(
        f'<a class="btn" href="/jobs{"" if s is None else "?status=" + s}">{esc(s or "all")}</a>'
        for s in (None, "new", "scored", "tailored", "applied", "skipped", "failed")
    )

    body = "<h1>Jobs</h1><p class='sub'>Sourced postings, best fit first.</p>"
    body += f'<div class="actions">{filters}</div><div style="height:12px"></div>'
    body += table(
        ["fit", "role", "company", "location", "status", "source"],
        [
            (
                score_bar(job.get("fit_score")),
                f'<a href="/jobs/{job["id"]}">{esc(job.get("title") or "Untitled")}</a>'
                + (
                    f'<div class="muted" style="font-size:12px">{esc(job.get("skip_reason"))}</div>'
                    if job.get("skip_reason")
                    else ""
                ),
                esc(job.get("company")),
                esc(job.get("location")) + (" " + pill("remote") if job.get("remote") else ""),
                pill(job.get("status") or "new", _tone(job.get("status"))),
                esc(job.get("source")),
            )
            for job in rows
        ],
        empty="No jobs sourced yet. Run the pipeline, or add sources to config.toml.",
    )
    return layout("Jobs", body, active="/jobs")


def job_detail(conn: sqlite3.Connection, job_id: int, config: Config, token: str) -> str | None:
    job = db.get_row(conn, "jobs", job_id)
    if not job:
        return None

    body = f"<h1>{esc(_job_title(job))}</h1>"
    links = ""
    if job.get("url"):
        links += f'<a href="{esc(job["url"])}" target="_blank" rel="noreferrer noopener">posting</a> '
    if job.get("apply_url"):
        links += f'<a href="{esc(job["apply_url"])}" target="_blank" rel="noreferrer noopener">apply form</a>'
    body += f"<p class='sub'>{links}</p>"

    body += "<div class='card'>" + kv(
        [
            ("Fit score", score_bar(job.get("fit_score"))),
            ("Status", pill(job.get("status") or "new", _tone(job.get("status")))),
            ("Source", esc(job.get("source"))),
            ("Location", esc(job.get("location"))),
            ("Compensation", esc(job.get("compensation"))),
            ("Posted", esc(job.get("posted_at"))),
            ("Discovered", esc(job.get("discovered_at"))),
            ("Skipped because", esc(job.get("skip_reason"))),
        ]
    ) + "</div>"

    existing = db.rows_to_dicts(
        conn.execute("SELECT * FROM applications WHERE job_id = ? ORDER BY id DESC", (job_id,)).fetchall()
    )
    if existing:
        body += "<h2>Applications</h2>"
        body += table(
            ["id", "status", "grounding", "created"],
            [
                (
                    f'<a href="/applications/{a["id"]}">#{a["id"]}</a>',
                    pill(a.get("status") or "", _tone(a.get("status"))),
                    pill(a.get("grounding_status") or "?", "good" if a.get("grounding_status") == "clean" else "warn"),
                    esc(a.get("approved_at") or a.get("sent_date") or ""),
                )
                for a in existing
            ],
        )
    else:
        body += (
            '<div class="actions">'
            + form_button(
                f"/jobs/{job_id}/tailor",
                "Tailor for this posting",
                token,
                style="primary",
                confirm="Tailoring makes one model API call. Continue?",
            )
            + "</div>"
        )

    body += "<h2>Posting</h2>"
    body += f'<div class="doc">{esc(job.get("description") or "")}</div>'
    return layout(_job_title(job), body, active="/jobs")


# --------------------------------------------------------------------------- queue


def queue(conn: sqlite3.Connection) -> str:
    rows = db.list_applications(conn)
    body = "<h1>Queue</h1><p class='sub'>Everything drafted, approved, or sent.</p>"
    body += table(
        ["id", "role", "company", "fit", "grounding", "status", "channel"],
        [
            (
                f'<a href="/applications/{a["id"]}">#{a["id"]}</a>',
                esc(a.get("role")),
                esc(a.get("company")),
                score_bar(a.get("fit_score")),
                pill(
                    a.get("grounding_status") or "?",
                    "good" if a.get("grounding_status") == "clean" else "warn",
                ),
                pill(a.get("status") or "", _tone(a.get("status"))),
                esc(a.get("channel")),
            )
            for a in rows
        ],
        empty="Nothing drafted yet.",
    )
    return layout("Queue", body, active="/queue")


def _read_bundle(resume_version: str | None) -> dict[str, str]:
    """Load the generated documents off disk, if the bundle still exists."""
    if not resume_version:
        return {}
    folder = Path(resume_version)
    if not folder.is_absolute():
        folder = db.PROJECT_ROOT / folder
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
    body = f"<h1>{esc(title)}</h1>"

    reasons: list[str] = []
    raw_reasons = app.get("decision_reasons")
    if raw_reasons:
        try:
            parsed = json.loads(raw_reasons)
            reasons = [str(r) for r in parsed] if isinstance(parsed, list) else [str(parsed)]
        except (ValueError, TypeError):
            reasons = [str(raw_reasons)]

    body += "<div class='card'>" + kv(
        [
            ("Status", pill(app.get("status") or "", _tone(app.get("status")))),
            ("Fit score", score_bar(app.get("fit_score"))),
            (
                "Grounding",
                pill(
                    app.get("grounding_status") or "unknown",
                    "good" if app.get("grounding_status") == "clean" else "warn",
                ),
            ),
            ("Channel", esc(app.get("channel"))),
            ("Source", esc(app.get("source"))),
            (
                "Posting",
                f'<a href="{esc(app["job_url"])}" target="_blank" rel="noreferrer noopener">link</a>'
                if app.get("job_url")
                else "",
            ),
            ("Bundle", f'<span class="mono">{esc(app.get("resume_version"))}</span>'),
            ("Approved", esc(app.get("approved_at"))),
            ("Sent", esc(app.get("sent_date"))),
            ("Dispatch error", f'<span style="color:var(--bad)">{esc(app.get("dispatch_error"))}</span>'
             if app.get("dispatch_error") else ""),
        ]
    ) + "</div>"

    if reasons:
        body += notice("Why the policy engine decided this:", reasons)

    status = (app.get("status") or "").lower()
    if status == "drafted":
        body += (
            '<div class="actions">'
            + form_button(f"/applications/{app_id}/approve", "Approve", token, style="primary")
            + form_button(f"/applications/{app_id}/reject", "Reject", token, style="danger")
            + "</div>"
        )
    elif status == "approved":
        body += notice(
            "Approved. This tool does not send from the browser -- run the pipeline, "
            "or send it yourself from the bundle folder.",
            tone="warn",
        )

    documents = _read_bundle(app.get("resume_version"))
    if not documents:
        body += notice(
            "The generated documents are not on disk at the recorded path.",
            tone="warn",
        )
    for name, content in documents.items():
        body += f"<h2>{esc(name)}</h2><div class='doc'>{esc(content)}</div>"

    return layout(title or "Application", body, active="/queue")


# --------------------------------------------------------------------------- profile


def profile(conn: sqlite3.Connection) -> str:
    g = graph_module.ProfileGraph.load(conn)
    counts = db.profile_counts(conn)
    evidence = db.skill_evidence_counts(conn)
    unevidenced = db.unevidenced_skills(conn)

    body = "<h1>Profile</h1><p class='sub'>The graph every resume is drawn from.</p>"

    if not g.experiences and not g.projects:
        body += notice(
            "The graph is empty. Import a LinkedIn export or a resume first.",
            tone="warn",
        )

    body += '<div class="grid">'
    for key in ("experiences", "achievements", "projects", "education", "skills"):
        body += stat(counts.get(key, 0), key)
    body += "</div>"

    if g.experiences:
        body += "<h2>Positions</h2>"
        for node in g.experiences:
            bullets = "".join(
                f"<li>{esc(a.row.get('description') or a.title)}"
                + (
                    f' <span class="muted">({esc(a.row.get("quantified_impact"))})</span>'
                    if a.row.get("quantified_impact")
                    else ""
                )
                + ("" if a.verified else " " + pill("unconfirmed", "warn"))
                + "</li>"
                for a in node.achievements
            )
            body += (
                f'<div class="card"><h3>{esc(node.label)}</h3>'
                f'<div class="muted mono" style="font-size:12px">{esc(node.dates)}</div>'
                + (
                    f'<ul class="tight">{bullets}</ul>'
                    if bullets
                    else '<div class="muted" style="margin-top:6px">No accomplishments recorded.</div>'
                )
                + "</div>"
            )

    if g.projects:
        body += "<h2>Projects</h2>"
        for node in g.projects:
            body += (
                f'<div class="card"><h3>{esc(node.row.get("name"))}</h3>'
                f'<div class="muted">{esc(node.row.get("description"))}</div></div>'
            )

    body += "<h2>Skills</h2>"
    body += table(
        ["skill", "evidence", "category"],
        [
            (
                esc(skill.get("name")),
                (
                    pill(f"{evidence.get(skill['id'], 0)} record(s)", "good")
                    if evidence.get(skill["id"])
                    else pill("none -- will never appear on a resume", "bad")
                ),
                esc(skill.get("category")),
            )
            for skill in db.list_skills(conn)
        ],
        empty="No skills recorded.",
    )

    if unevidenced:
        body += notice(
            f"{len(unevidenced)} skill(s) have no supporting record, so they are locked "
            "out of every resume:",
            [s["name"] for s in unevidenced],
            tone="warn",
        )
    return layout("Profile", body, active="/profile")


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
    body = (
        "<h1>Review</h1>"
        "<p class='sub'>Rows a model extracted from your documents. Confirm them and "
        "<code>tailor --verified-only</code> will use them.</p>"
    )
    found = False
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
        found = True
        body += f"<h2>{esc(name)} ({len(rows)})</h2>"
        body += table(
            ["id", "what", ""],
            [
                (
                    f'<span class="mono">{row["id"]}</span>',
                    esc(
                        row.get("title")
                        or row.get("name")
                        or row.get("description")
                        or row.get("degree")
                        or "(no label)"
                    ),
                    form_button(f"/review/{name}/{row['id']}/verify", "Confirm", token),
                )
                for row in rows
            ],
        )
    if not found:
        body += notice("Nothing awaiting review. Every row is confirmed.", tone="")
    return layout("Review", body, active="/review")


# --------------------------------------------------------------------------- runs


def runs(conn: sqlite3.Connection) -> str:
    rows = db.rows_to_dicts(
        conn.execute("SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT 100").fetchall()
    )
    body = "<h1>Runs</h1><p class='sub'>One row per pipeline run, for auditing an unattended night.</p>"
    body += table(
        ["id", "mode", "started", "finished", "notes"],
        [
            (
                f'<span class="mono">{r["id"]}</span>',
                pill(r.get("mode") or ""),
                esc(r.get("started_at")),
                esc(r.get("finished_at")) or '<span class="muted">did not finish</span>',
                esc(r.get("summary") or r.get("notes") or ""),
            )
            for r in rows
        ],
        empty="No runs recorded yet.",
    )
    return layout("Runs", body, active="/runs")


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

    body = "<h1>Answers</h1>"
    body += (
        '<p class="muted">Forms ask things a resume does not cover. Write each answer '
        "once here and applications fill from it. Nothing on this page is ever "
        "generated -- what you type is exactly what gets submitted.</p>"
    )

    if gaps:
        rows = ""
        for gap in gaps:
            question = str(gap.get("question") or "")
            scope = f" &middot; {esc(gap['company'])}" if gap.get("company") else ""
            rows += (
                '<div class="answer-row"><div style="flex:1">'
                f'<div><span class="count">{int(gap.get("seen_count") or 1)}&times;</span> '
                f"{esc(question)}{scope}</div>"
                + form(
                    "/answers/add",
                    token,
                    field("pattern", "", question[:60], placeholder="question to match")
                    + field("answer", "", "", placeholder="your answer"),
                    "Answer it",
                )
                + "</div></div>"
            )
        body += (
            '<div class="card">'
            "<h2>Blocking your applications</h2>"
            '<p class="muted">These stopped a real application. Answer one and it is '
            "covered on every future posting that asks it.</p>" + rows + "</div>"
        )

    if stored:
        rows = ""
        for item in stored:
            scope = f' <span class="muted">&middot; {esc(item.company)}</span>' if item.company else ""
            rows += (
                '<div class="answer-row"><div>'
                f'<div class="pattern">{esc(item.pattern)}{scope}</div>'
                f'<div class="value">{esc(item.answer)}</div></div>'
                + form_button(f"/answers/{item.id}/delete", "Delete", token, style="danger")
                + "</div>"
            )
        body += f'<div class="card"><h2>Stored ({len(stored)})</h2>{rows}</div>'

    known = {a.pattern for a in stored}
    suggestions = [q for q in COMMON_QUESTIONS if q[0] not in known]
    if suggestions:
        rows = ""
        for pattern, label, hint in suggestions:
            rows += (
                '<div class="answer-row"><div style="flex:1">'
                + form(
                    "/answers/add",
                    token,
                    f'<input type="hidden" name="pattern" value="{esc(pattern)}">'
                    + field("answer", label, "", hint=hint, placeholder=hint),
                    "Save",
                )
                + "</div></div>"
            )
        body += (
            '<div class="card"><h2>Common questions</h2>'
            '<p class="muted">Filling these in covers most application forms. '
            "Skip any that do not apply to you.</p>" + rows + "</div>"
        )

    body += (
        '<div class="card"><h2>Add your own</h2>'
        + form(
            "/answers/add",
            token,
            '<div class="grid2">'
            + field(
                "pattern", "Question contains", "", placeholder="visa sponsorship",
                hint="Matched against the form's question, case-insensitive.",
            )
            + field(
                "company", "Only for company (optional)", "", placeholder="Anthropic",
                hint="Leave blank to use for every employer.",
            )
            + "</div>"
            + field(
                "answer", "Answer", "", kind="textarea",
                placeholder="Exactly what should be entered",
            ),
            "Add answer",
        )
        + "</div>"
    )
    return layout("Answers", body, active="/answers")


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

    core = "".join(
        field(name, label, current.get(name, ""), kind=kind, hint=hint)
        for name, label, kind, hint in PROFILE_FIELDS
    )
    body = "<h1>Your details</h1>"
    body += (
        '<p class="muted">What gets typed into application forms. Anything blank here '
        "is a field an application can stop on.</p>"
    )
    missing = [label for name, label, _k, _h in PROFILE_FIELDS if not current.get(name)]
    if missing:
        body += notice("Not filled in yet", missing, tone="warn")

    body += (
        '<div class="card">'
        + form(
            "/profile/save",
            token,
            f'<div class="grid2">{core}</div>'
            + field(
                "summary", "Summary", current.get("summary", ""), kind="textarea", rows=4,
                hint="A few lines about you. Used for tone, never copied verbatim.",
            ),
            "Save details",
        )
        + "</div>"
    )

    if extra:
        rows = "".join(
            '<div class="answer-row"><div>'
            f'<div class="pattern">{esc(key)}</div>'
            f'<div class="value">{esc(value)}</div></div>'
            + form_button(f"/profile/attr/{key}/delete", "Delete", token, style="danger")
            + "</div>"
            for key, value in sorted(extra.items())
        )
        body += f'<div class="card"><h2>Other details</h2>{rows}</div>'

    body += (
        '<div class="card"><h2>Add anything else</h2>'
        '<p class="muted">Pronouns, clearance level, salary floor, visa status -- '
        "anything a form might ask that has no box above.</p>"
        + form(
            "/profile/save",
            token,
            '<div class="grid2">'
            + field("key", "Name", "", placeholder="security_clearance")
            + field("value", "Value", "", placeholder="Secret, active")
            + "</div>",
            "Add detail",
        )
        + "</div>"
    )
    return layout("Your details", body, active="/profile/edit")


# --------------------------------------------------------------------------- profile builder


def _dates(start: Any, end: Any, current: Any = 0) -> str:
    start = esc(start) or "?"
    if current and not end:
        return f"{start} &ndash; present"
    return f"{start} &ndash; {esc(end) or 'present'}"


def _delete(entity: str, row_id: Any, token: str, what: str) -> str:
    return form_button(
        f"/profile/{entity}/{row_id}/delete", "Delete", token,
        style="danger", confirm=f"Delete {what}? This cannot be undone.",
    )


def profile_build(conn: sqlite3.Connection, token: str) -> str:
    """Enter your history here; resumes are generated from it.

    Laid out the way the graph is actually shaped: accomplishments sit under the
    position they happened at, because that is the constraint the schema
    enforces and the reason a generated resume can place a bullet under the
    right employer without the model guessing.
    """
    graph = graph_module.ProfileGraph.load(conn)
    body = "<h1>Your history</h1>"
    body += (
        '<p class="muted">Everything a resume is built from. Nothing here is generated -- '
        "tailoring selects from these rows and writes prose for them, it never adds a fact "
        "that is not on this page.</p>"
    )

    counts = graph.counts()
    unevidenced = db.unevidenced_skills(conn)
    if not graph.experiences:
        body += notice(
            "No positions yet. Add one below, then add the things you did there -- "
            "an accomplishment has to belong to a position, project, or degree.",
            tone="warn",
        )

    # ---------------------------------------------------------------- positions
    body += "<h2>Positions</h2>"
    for node in graph.experiences:
        record = node.row
        exp_id = record.get("id")
        header = (
            f'<div class="row-head"><div>'
            f'<strong>{esc(record.get("title"))}</strong>'
            f'{" &middot; " + esc(record.get("organization")) if record.get("organization") else ""}'
            f'<div class="muted" style="font-size:13px">'
            f'{_dates(record.get("start_date"), record.get("end_date"), record.get("is_current"))}'
            f'{" &middot; " + esc(record.get("location")) if record.get("location") else ""}</div>'
            f"</div>{_delete('experience', exp_id, token, 'this position and everything under it')}</div>"
        )
        bullets = ""
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
            bullets += (
                '<li><div class="ach">'
                f"<div><strong>{esc(title)}</strong>"
                + (f'<div class="muted">{esc(detail)}</div>' if detail else "")
                + (f'<div class="impact">{esc(impact)}</div>' if impact else "")
                + "</div>"
                + _delete("achievement", achievement.row.get("id"), token, "this accomplishment")
                + "</div></li>"
            )
        bullets = f'<ul class="tight">{bullets}</ul>' if bullets else (
            '<p class="muted" style="font-size:13px">No accomplishments yet. '
            "These are what a resume is actually made of.</p>"
        )
        add = form(
            "/profile/achievement/add",
            token,
            f'<input type="hidden" name="experience_id" value="{esc(exp_id)}">'
            + '<div class="grid2">'
            + field("title", "What you did", "", placeholder="Rebuilt the checkout API")
            + field("impact", "Measurable result (optional)", "",
                    placeholder="cut p95 latency 40%",
                    hint="Only a number you can point at. Invented metrics are what grounding catches.")
            + "</div>"
            + field("description", "Detail", "", kind="textarea", rows=2,
                    placeholder="What the work was, in a sentence or two.")
            + field("skills", "Skills used (comma separated)", "",
                    placeholder="Python, PostgreSQL",
                    hint="Each becomes evidence that you have used that skill."),
            "Add accomplishment",
        )
        body += f'<div class="card">{header}{bullets}<details><summary>Add accomplishment</summary>{add}</details></div>'

    body += (
        '<div class="card"><h3>Add a position</h3>'
        + form(
            "/profile/experience/add",
            token,
            '<div class="grid2">'
            + field("title", "Title", "", placeholder="Senior Software Engineer")
            + field("org", "Company", "", placeholder="Acme Corp")
            + field("start", "Started", "", placeholder="2021-03")
            + field("end", "Ended", "", placeholder="leave blank if current")
            + field("location", "Location", "", placeholder="Austin, TX")
            + field("type", "Employment type", "full-time",
                    kind="select",
                    options=["full-time", "part-time", "contract", "internship", "freelance"])
            + "</div>"
            + field("skills", "Skills (comma separated)", "", placeholder="Python, AWS"),
            "Add position",
        )
        + "</div>"
    )

    # ---------------------------------------------------------------- education
    body += "<h2>Education</h2>"
    for record in db.list_education(conn):
        body += (
            '<div class="card"><div class="row-head"><div>'
            f'<strong>{esc(record.get("degree"))}</strong>'
            f'{" &middot; " + esc(record.get("organization")) if record.get("organization") else ""}'
            f'<div class="muted" style="font-size:13px">'
            f'{esc(record.get("field_of_study"))} {_dates(record.get("start_date"), record.get("end_date"))}</div>'
            "</div>"
            + _delete("education", record.get("id"), token, "this degree")
            + "</div></div>"
        )
    body += (
        '<div class="card"><h3>Add education</h3>'
        + form(
            "/profile/education/add",
            token,
            '<div class="grid2">'
            + field("title", "Degree", "", placeholder="BS Computer Science")
            + field("org", "School", "", placeholder="University of Texas")
            + field("field", "Field of study", "", placeholder="Computer Science")
            + field("start", "Started", "", placeholder="2015")
            + field("end", "Finished", "", placeholder="2019")
            + "</div>",
            "Add education",
        )
        + "</div>"
    )

    # ---------------------------------------------------------------- projects
    body += "<h2>Projects</h2>"
    for node in graph.projects:
        record = node.row
        body += (
            '<div class="card"><div class="row-head"><div>'
            f'<strong>{esc(record.get("name"))}</strong>'
            f'<div class="muted" style="font-size:13px">{esc(record.get("description"))}</div></div>'
            + _delete("project", record.get("id"), token, "this project")
            + "</div></div>"
        )
    body += (
        '<div class="card"><h3>Add a project</h3>'
        + form(
            "/profile/project/add",
            token,
            '<div class="grid2">'
            + field("title", "Name", "", placeholder="Open-source scheduler")
            + field("role", "Your role", "", placeholder="Creator")
            + field("url", "Link", "", placeholder="https://github.com/...")
            + field("skills", "Skills (comma separated)", "", placeholder="Go, Kubernetes")
            + "</div>"
            + field("description", "What it is", "", kind="textarea", rows=2),
            "Add project",
        )
        + "</div>"
    )

    # ---------------------------------------------------------------- certifications
    body += "<h2>Certifications</h2>"
    for record in db.rows_to_dicts(conn.execute("SELECT * FROM certifications ORDER BY IFNULL(issue_date, '') DESC")):
        body += (
            '<div class="card"><div class="row-head"><div>'
            f'<strong>{esc(record.get("name"))}</strong>'
            f'{" &middot; " + esc(record.get("issuer")) if record.get("issuer") else ""}'
            f'<div class="muted" style="font-size:13px">{esc(record.get("issue_date"))}</div></div>'
            + _delete("certification", record.get("id"), token, "this certification")
            + "</div></div>"
        )
    body += (
        '<div class="card"><h3>Add a certification</h3>'
        + form(
            "/profile/certification/add",
            token,
            '<div class="grid2">'
            + field("title", "Name", "", placeholder="AWS Solutions Architect")
            + field("org", "Issuer", "", placeholder="Amazon Web Services")
            + field("start", "Issued", "", placeholder="2024-06")
            + field("url", "Credential link", "", placeholder="https://...")
            + "</div>",
            "Add certification",
        )
        + "</div>"
    )

    # ---------------------------------------------------------------- skills
    body += "<h2>Skills</h2>"
    evidenced = graph.evidenced_skills
    body += (
        f'<p class="muted">{len(evidenced)} with evidence, {len(unevidenced)} without. '
        "A skill with no evidence never reaches a resume, however loudly a posting asks "
        "for it -- attach it to a position or accomplishment above to make it usable.</p>"
    )
    if evidenced:
        body += '<div class="card">' + " ".join(
            pill(f'{esc(s.get("name"))} &middot; {s.get("evidence_count", 0)}', "good")
            for s in evidenced[:80]
        ) + "</div>"
    if unevidenced:
        body += (
            '<div class="card">'
            + notice(
                "These are claimed but nothing proves them, so they stay off every resume:",
                [str(s.get("name")) for s in unevidenced[:40]],
                tone="warn",
            )
            + "</div>"
        )

    body += (
        '<div class="card"><h3>Add a skill</h3>'
        '<p class="muted">Adding a skill here records the claim. It only becomes usable '
        "once something demonstrates it -- list it on a position or accomplishment above, "
        "or run <span class=\"mono\">jobsearch link</span> to scan your records for it.</p>"
        + form(
            "/profile/skill/add",
            token,
            '<div class="grid2">'
            + field("name", "Skill", "", placeholder="PostgreSQL")
            + field("proficiency", "Proficiency", "working", kind="select",
                    options=["familiar", "working", "advanced", "expert"])
            + "</div>",
            "Add skill",
        )
        + "</div>"
    )

    body += (
        f'<p class="muted" style="margin-top:26px">'
        f'{counts.get("experiences", 0)} positions &middot; '
        f'{counts.get("accomplishments", 0)} accomplishments &middot; '
        f'{counts.get("skills", 0)} skills</p>'
    )
    return layout("Your history", body, active="/profile/build")
