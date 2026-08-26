"""Tool definitions. See jobsearch/mcp/__init__.py for what this is and why.

Each tool opens its own connection via db.session() and closes it before
returning, matching the CLI's per-command pattern rather than holding one
connection open for the process lifetime -- MCP tool calls are infrequent
and this way a long-idle session never holds a stale connection.
"""

from __future__ import annotations

import hashlib
import sqlite3
from typing import Any

from mcp.server.mcpserver import MCPServer

from .. import db, matching, pipeline
from ..config import Config
from ..sourcing import Posting, list_jobs, store
from ..sourcing import competitions as competitions_sourcing

mcp = MCPServer("hole", description="Search, tailor, and track job applications and competitions -- the same local pipeline the CLI and web UI already use.")


def _config() -> Config:
    config = Config.load()
    if config is None:
        raise RuntimeError("no config.toml found -- run `python -m jobsearch init` first")
    return config


@mcp.tool()
def search_jobs(query: str = "", status: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """Search sourced job postings.

    query: matched against title, company, and location (case-insensitive substring).
    status: filter to one status -- new, scored, tailored, applied, skipped, failed.
    limit: max rows returned, newest/best-fit first.
    """
    with db.session() as conn:
        rows = list_jobs(conn, status=status or None, limit=None)
    if query:
        q = query.lower()
        rows = [
            r for r in rows
            if q in (r.get("title") or "").lower()
            or q in (r.get("company") or "").lower()
            or q in (r.get("location") or "").lower()
        ]
    return rows[:limit]


@mcp.tool()
def get_job(job_id: int) -> dict[str, Any] | None:
    """Full detail for one sourced job posting, by id."""
    with db.session() as conn:
        return db.get_row(conn, "jobs", job_id)


@mcp.tool()
def add_job(
    title: str, company: str, url: str = "", description: str = "", location: str = "",
) -> dict[str, Any]:
    """Add a job posting found outside the automated sources -- a referral, a
    link someone sent you, a board this app doesn't source from yet.

    It enters the pipeline exactly like an auto-sourced posting: scored
    against the profile immediately, then eligible for search_jobs and
    tailor_job like anything else. If a posting with the same
    company/title/location was already sourced, this returns the existing
    one instead of creating a duplicate.
    """
    external_id = hashlib.sha1(f"manual:{title}:{company}:{url}".encode()).hexdigest()[:16]
    posting = Posting(
        source="manual", external_id=external_id, company=company, title=title,
        location=location, url=url, description=description,
    )
    with db.session() as conn:
        new, duplicates = store(conn, [posting])
        row = conn.execute(
            "SELECT * FROM jobs WHERE fingerprint = ?", (posting.fingerprint(),)
        ).fetchone()
        job = db.row_to_dict(row)
        if new and job and description:
            g = _graph_or_none(conn)
            if g:
                score = matching.fit_score(posting.text, g.match_docs())
                db.update_row(conn, "jobs", job["id"], {"fit_score": score, "status": "scored"})
                job["fit_score"] = score
                job["status"] = "scored"
    return {"job": job, "created": bool(new), "already_existed": bool(duplicates)}


def _graph_or_none(conn: sqlite3.Connection):
    from .. import graph
    g = graph.ProfileGraph.load(conn)
    return None if g.is_empty() else g


@mcp.tool()
def tailor_job(job_id: int) -> dict[str, Any]:
    """Generate a tailored resume + cover letter for one posting and drop it
    in the review queue as a drafted application. Costs one model API call.
    If this job already has an application, returns that one instead of
    generating a duplicate -- calling this twice on the same job is safe.
    """
    config = _config()
    with db.session() as conn:
        try:
            app_id = pipeline.tailor_one(conn, config, job_id)
        except pipeline.TailorError as exc:
            return {"error": str(exc)}
        app = db.get_row(conn, "applications", app_id)
    return {"application": app}


@mcp.tool()
def list_queue(status: str = "drafted") -> list[dict[str, Any]]:
    """Applications waiting for a decision. status: drafted, approved, sent,
    rejected, or responded. Empty string returns every status."""
    with db.session() as conn:
        return db.list_applications(conn, status=status or None)


@mcp.tool()
def approve_application(application_id: int) -> dict[str, Any]:
    """Approve a drafted application. This does not send it -- sending only
    happens when the pipeline runs with autonomous mode on in config.toml,
    same as approving from the web UI. Approving just clears it to go out
    on the next run."""
    with db.session() as conn:
        ok = db.update_application(
            conn, application_id, {"status": "approved", "approved_at": db.now()}
        )
        if not ok:
            return {"error": f"no application {application_id}"}
        return {"application": db.get_row(conn, "applications", application_id)}


@mcp.tool()
def reject_application(application_id: int) -> dict[str, Any]:
    """Reject a drafted application. It stays in the database, marked
    rejected, and is never sent."""
    with db.session() as conn:
        ok = db.update_application(conn, application_id, {"status": "rejected"})
        if not ok:
            return {"error": f"no application {application_id}"}
        return {"application": db.get_row(conn, "applications", application_id)}


@mcp.tool()
def profile_summary() -> dict[str, Any]:
    """Counts of everything in the profile graph -- positions, projects,
    skills (evidenced vs. not), education, certifications -- plus the
    stored name/headline/location. Read-only; use the web UI's
    /profile/build to add or edit entries."""
    with db.session() as conn:
        counts = db.profile_counts(conn)
        evidenced = len(db.skill_evidence_counts(conn))
        unevidenced = db.unevidenced_skills(conn)
        row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    return {
        "profile": db.row_to_dict(row),
        "counts": counts,
        "skills_evidenced": evidenced,
        "skills_unevidenced": unevidenced,
    }


@mcp.tool()
def list_competitions(status: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """Hackathons, case competitions, and finance competitions -- both
    entered by hand and found automatically. status: 'discovered' for
    open opportunities not yet decided on, 'entered' (or blank) for
    everything, ordered soonest-deadline-first."""
    with db.session() as conn:
        sql = "SELECT * FROM competitions"
        params: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY (deadline IS NULL), deadline, id DESC LIMIT ?"
        params.append(limit)
        return db.rows_to_dicts(conn.execute(sql, params).fetchall())


@mcp.tool()
def discover_competitions() -> dict[str, Any]:
    """Search public sources (currently Devpost) for open competitions and
    add any new ones. Same connector the pipeline already runs
    automatically on every `jobsearch run` -- this triggers it on demand."""
    with db.session() as conn:
        found, errors = competitions_sourcing.discover()
        added, skipped = competitions_sourcing.save(conn, found)
    return {"found": len(found), "added": added, "already_tracked": skipped, "errors": errors}


@mcp.tool()
def run_pipeline(dry_run: bool = True) -> dict[str, Any]:
    """Run a full pipeline pass: source jobs, find competitions, score,
    tailor up to the configured limit, and dispatch anything that clears
    every policy check. Whether anything actually SENDS depends entirely on
    config.toml's `autonomous` setting -- this tool does not and cannot
    override that; if it's off (the default), everything lands in the
    review queue no matter what dry_run says here. dry_run additionally
    stops short of any real dispatch attempt even in autonomous mode, so it
    is the safe way to see what a run would do."""
    config = _config()
    with db.session() as conn:
        report = pipeline.run(conn, config, dry_run=dry_run)
    return {
        "mode": report.mode,
        "sourced": report.sourced,
        "duplicates": report.duplicates,
        "competitions_found": report.competitions_found,
        "scored": report.scored,
        "screened_out": report.screened_out,
        "tailored": report.tailored,
        "queued": report.queued,
        "sent": report.sent,
        "errors": report.errors,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
