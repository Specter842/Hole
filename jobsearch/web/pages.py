"""The views. Each returns a full HTML page.

These read the same tables the CLI reads, through the same `db` helpers, so the
two front ends can never drift into disagreeing about what is in the database.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .. import db, graph as graph_module, llm, policy
from ..config import Config
from .html import (
    esc,
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
