"""The unattended run: source -> score -> screen -> tailor -> verify -> decide -> dispatch.

One pass is one `run()`. Everything it does lands in the database -- the jobs it
saw, the fit it computed, why it skipped what it skipped, what it generated, what
the grounding check found, what the policy decided and on what grounds, and
whether dispatch succeeded. A run you cannot reconstruct afterwards is not one
that should be allowed to email people.

Failure is always local. A dead job board, a posting that will not tailor, a
form that will not fill: each is recorded and the run continues.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import db, generate, graph, matching, policy, render, retrieval, sourcing, verify
from .config import Config
from .dispatch import DispatchResult, ats_form, email_gmail, find_apply_email


@dataclass
class RunReport:
    run_id: int | None = None
    mode: str = "review-only"
    sourced: int = 0
    duplicates: int = 0
    scored: int = 0
    screened_out: int = 0
    tailored: int = 0
    queued: int = 0
    sent: int = 0
    errors: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    def note(self, line: str) -> None:
        self.log.append(line)

    def fail(self, line: str) -> None:
        self.errors.append(line)
        self.log.append(f"ERROR {line}")


def _slug(company: str | None, role: str | None, job_id: int) -> str:
    return (
        f"{date.today().isoformat()}_{generate.slugify(company, 'company')}"
        f"_{generate.slugify(role, 'role')}_{job_id}"
    )


def write_bundle(
    out_dir: Path,
    *,
    result: generate.TailoredOutput,
    job_description: str,
    plan: retrieval.ResumePlan,
    meta: dict[str, Any],
) -> list[Path]:
    """Documents plus the provenance record, so any draft can be traced later."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in (
        ("resume.md", result.resume),
        ("cover_letter.md", result.cover_letter),
        ("fit_notes.md", result.fit_notes),
        ("job_description.txt", job_description),
        ("raw_response.md", result.raw),
    ):
        if content and content.strip():
            path = out_dir / name
            path.write_text(content.strip() + "\n", encoding="utf-8")
            written.append(path)

    (out_dir / "sources.json").write_text(
        json.dumps(
            {
                **meta,
                "model": result.model,
                "usage": result.usage,
                "fit_score": plan.fit,
                "experiences_used": [
                    {
                        "id": p.node.id,
                        "label": p.node.label,
                        "relative": p.relative,
                        "bullet_ids": [b.id for b in p.bullets],
                    }
                    for p in plan.experiences
                ],
                "skills_claimed": plan.skills,
                "uncovered_requirements": plan.gaps,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return written


# --------------------------------------------------------------------------- stages


def source_jobs(conn: sqlite3.Connection, config: Config, report: RunReport) -> None:
    result = sourcing.collect(config)
    new, duplicates = sourcing.store(conn, result.postings)
    conn.commit()
    report.sourced = new
    report.duplicates = duplicates
    for source, count in sorted(result.per_source.items()):
        report.note(f"  {source}: {count} posting(s) returned")
    for error in result.errors:
        report.fail(error)
    report.note(f"Sourced {new} new posting(s), {duplicates} already seen.")


def score_jobs(conn: sqlite3.Connection, g: graph.ProfileGraph, report: RunReport) -> None:
    """Fit score for every posting we have not scored yet. No API calls."""
    docs = g.match_docs()
    pending = sourcing.list_jobs(conn, status="new", order="id ASC")
    for job in pending:
        text = f"{job.get('title') or ''}\n{job.get('description') or ''}"
        fit = matching.fit_score(text, docs)
        db.update_row(conn, "jobs", int(job["id"]), {"fit_score": fit, "status": "scored"})
        report.scored += 1
    conn.commit()
    if report.scored:
        report.note(f"Scored {report.scored} posting(s) against the profile.")


def _job_description(job: dict[str, Any]) -> str:
    return (
        f"{job.get('title') or ''}\n"
        f"{job.get('company') or ''}\n"
        f"{job.get('location') or ''}\n\n"
        f"{job.get('description') or ''}"
    )


def _dispatch(
    conn: sqlite3.Connection,
    config: Config,
    job: dict[str, Any],
    plan: retrieval.ResumePlan,
    result: generate.TailoredOutput,
    out_dir: Path,
    slug: str,
    *,
    dry_run: bool,
) -> DispatchResult:
    channel = policy.available_channel(job, config)

    if channel == "ats_form":
        resume_md = out_dir / "resume.md"
        resume_pdf = None
        if resume_md.is_file():
            html_path = render.write_html(resume_md, "Resume")
            resume_pdf, _message = render.write_pdf(html_path)
        fields = ats_form.ApplicantFields.from_profile(
            plan.profile,
            resume_path=resume_pdf,
            cover_letter_text=result.cover_letter,
        )
        return ats_form.submit(
            config.dispatch.ats,
            apply_url=str(job.get("apply_url") or job.get("url") or ""),
            fields=fields,
            project_root=db.PROJECT_ROOT,
            slug=slug,
            dry_run=dry_run,
        )

    if channel == "email":
        recipient = find_apply_email(job.get("description"), job.get("url"))
        if not recipient:
            return DispatchResult(
                False,
                "email",
                "the posting names no address to apply to, and guessing one would be spam",
            )
        attachments = [p for p in (out_dir / "resume.md",) if p.is_file()]
        html_path = render.write_html(out_dir / "resume.md", "Resume") if attachments else None
        if html_path:
            pdf_path, _ = render.write_pdf(html_path)
            if pdf_path:
                attachments = [pdf_path]
        subject = f"{plan.profile.get('full_name', 'Application')} - {job.get('title')}"
        return email_gmail.send(
            config.dispatch.email,
            db.PROJECT_ROOT,
            to=recipient,
            subject=subject,
            body=result.cover_letter,
            attachments=attachments,
            dry_run=dry_run,
        )

    return DispatchResult(False, "none", "no dispatch channel available for this posting")


def process_job(
    conn: sqlite3.Connection,
    config: Config,
    g: graph.ProfileGraph,
    job: dict[str, Any],
    context: policy.PolicyContext,
    report: RunReport,
    *,
    dry_run: bool,
) -> None:
    job_id = int(job["id"])
    job_description = _job_description(job)

    plan = retrieval.build_plan(
        g,
        job_description,
        company=job.get("company"),
        role=job.get("title"),
        verified_only=config.dispatch.require_verified_records,
    )
    if plan.is_empty():
        db.update_row(
            conn, "jobs", job_id,
            {"status": "skipped", "skip_reason": "nothing in the profile matched"},
        )
        report.screened_out += 1
        report.note(f"  skip  {job.get('company')} / {job.get('title')}: no matching experience")
        return

    try:
        result = generate.generate(job_description, plan)
    except generate.GenerationError as exc:
        db.update_row(conn, "jobs", job_id, {"status": "failed", "skip_reason": str(exc)[:200]})
        report.fail(f"{job.get('company')} / {job.get('title')}: {exc}")
        return

    context.tailored_this_run += 1
    report.tailored += 1

    slug = _slug(job.get("company"), job.get("title"), job_id)
    out_dir = db.PROJECT_ROOT / "output" / slug
    write_bundle(
        out_dir,
        result=result,
        job_description=job_description,
        plan=plan,
        meta={
            "generated": date.today().isoformat(),
            "job_id": job_id,
            "company": job.get("company"),
            "role": job.get("title"),
            "job_url": job.get("url"),
            "source": job.get("source"),
        },
    )

    findings = verify.verify_plan(
        {"resume": result.resume, "cover_letter": result.cover_letter},
        plan.to_facts(),
        target_company=job.get("company"),
    )
    used_unverified = any(
        not p.node.row.get("verified") for p in plan.experiences
    )

    decision = policy.decide_dispatch(
        job,
        config,
        context,
        grounding_findings=findings,
        missing_profile_fields=plan.missing_profile_fields,
        used_unverified=used_unverified,
    )

    application_id = db.insert_application(
        conn,
        {
            "job_id": job_id,
            "company": job.get("company"),
            "role": job.get("title"),
            "source": job.get("source"),
            "job_url": job.get("url"),
            "resume_version": slug,
            "status": "drafted",
            "fit_score": plan.fit,
            "grounding_status": "flagged" if findings else "clean",
            "decision_reasons": json.dumps(decision.reasons),
        },
    )
    db.update_row(conn, "jobs", job_id, {"status": "tailored"})
    conn.commit()

    label = f"{job.get('company')} / {job.get('title')}"
    if not decision.sends:
        report.queued += 1
        report.note(f"  queue {label} (fit {plan.fit:.0f}) -- {'; '.join(decision.reasons)}")
        return

    dispatch_result = _dispatch(
        conn, config, job, plan, result, out_dir, slug, dry_run=dry_run
    )
    if dispatch_result.ok:
        db.update_application(
            conn,
            application_id,
            {
                "status": "sent",
                "channel": dispatch_result.channel,
                "approved_at": db.now(),
                "sent_date": date.today().isoformat(),
                "attempts": 1,
            },
        )
        db.update_row(conn, "jobs", job_id, {"status": "applied"})
        context.record_sent(job.get("company"))
        report.sent += 1
        report.note(f"  SENT  {label} (fit {plan.fit:.0f}) -- {dispatch_result}")
    else:
        db.update_application(
            conn,
            application_id,
            {
                "status": "drafted",
                "channel": dispatch_result.channel,
                "dispatch_error": dispatch_result.detail[:400],
                "attempts": 1,
            },
        )
        report.queued += 1
        report.note(f"  queue {label} -- dispatch failed: {dispatch_result.detail}")
    conn.commit()


# --------------------------------------------------------------------------- entry point


def run(
    conn: sqlite3.Connection,
    config: Config,
    *,
    dry_run: bool = False,
    skip_sourcing: bool = False,
    limit: int | None = None,
) -> RunReport:
    mode = "dry-run" if dry_run else ("autonomous" if config.autonomous else "review-only")
    report = RunReport(mode=mode)

    report.run_id = db.insert_row(
        conn, "pipeline_runs", {"started_at": db.now(), "mode": mode}
    )
    conn.commit()

    g = graph.ProfileGraph.load(conn)
    if g.is_empty():
        report.fail("The profile graph is empty -- import your history before running.")
        _finish(conn, report)
        return report

    if not skip_sourcing:
        source_jobs(conn, config, report)
    score_jobs(conn, g, report)

    context = policy.PolicyContext.load(conn)
    candidates = sourcing.list_jobs(conn, status="scored")

    ceiling = limit if limit is not None else config.limits.max_tailor_per_run
    report.note("")
    report.note(f"Reviewing {len(candidates)} scored posting(s), tailoring at most {ceiling}:")

    for job in candidates:
        screened = policy.screen(job, config, context)
        if screened.action == policy.SKIP:
            db.update_row(
                conn, "jobs", int(job["id"]),
                {"status": "skipped", "skip_reason": "; ".join(screened.reasons)},
            )
            report.screened_out += 1
            continue
        if context.tailored_this_run >= ceiling:
            continue
        process_job(conn, config, g, job, context, report, dry_run=dry_run)

    conn.commit()
    _finish(conn, report)
    return report


def _finish(conn: sqlite3.Connection, report: RunReport) -> None:
    if report.run_id:
        db.update_row(
            conn,
            "pipeline_runs",
            report.run_id,
            {
                "finished_at": db.now(),
                "sourced": report.sourced,
                "scored": report.scored,
                "tailored": report.tailored,
                "queued": report.queued,
                "sent": report.sent,
                "skipped": report.screened_out,
                "errors": len(report.errors),
                "notes": "\n".join(report.errors[:20]) or None,
            },
        )
        conn.commit()
