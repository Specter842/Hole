"""Turn a job description plus the profile graph into a ResumePlan.

This is the step the whole design turns on: **selection is deterministic, only
phrasing is generative.** Code decides which positions appear, which bullets sit
under each, and which skills are allowed to be claimed. The model receives that
plan and writes prose for it. It never gets to choose what is true.

Consequences worth stating plainly:
  - A skill with no `skill_evidence` row cannot reach a resume, no matter how
    loudly the posting asks for it.
  - Bullets stay attached to the position they happened at, so dates and
    employers are structural rather than remembered.
  - Whatever the posting wants that the profile cannot support comes back as an
    explicit gap list instead of being quietly smoothed over.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any, Sequence

from . import matching
from .graph import AchievementNode, EducationNode, ExperienceNode, ProfileGraph, ProjectNode


@dataclass
class PlannedExperience:
    node: ExperienceNode
    score: float
    relative: float
    bullets: list[AchievementNode] = dc_field(default_factory=list)
    matched_terms: list[str] = dc_field(default_factory=list)
    kept_for_continuity: bool = False

    def to_fact(self) -> dict[str, Any]:
        return self.node.to_fact(self.bullets)


@dataclass
class PlannedProject:
    node: ProjectNode
    score: float
    relative: float

    def to_fact(self) -> dict[str, Any]:
        return self.node.to_fact()


@dataclass
class ResumePlan:
    profile: dict[str, Any]
    company: str | None
    role: str | None
    fit: float
    experiences: list[PlannedExperience] = dc_field(default_factory=list)
    projects: list[PlannedProject] = dc_field(default_factory=list)
    education: list[EducationNode] = dc_field(default_factory=list)
    certifications: list[Any] = dc_field(default_factory=list)
    skills: list[str] = dc_field(default_factory=list)
    other_skills: list[str] = dc_field(default_factory=list)
    gaps: list[str] = dc_field(default_factory=list)
    unevidenced_requests: list[str] = dc_field(default_factory=list)
    missing_profile_fields: list[str] = dc_field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.experiences or self.projects)

    def bullet_count(self) -> int:
        return sum(len(e.bullets) for e in self.experiences)

    def to_facts(self) -> dict[str, Any]:
        """The closed set of facts handed to the model. Nothing else is permitted."""
        return {
            "candidate_profile": self.profile,
            "target": {"company": self.company, "role": self.role},
            "fit_score": self.fit,
            "skills_you_may_claim": self.skills,
            "other_evidenced_skills": self.other_skills,
            "experience": [e.to_fact() for e in self.experiences],
            "projects": [p.to_fact() for p in self.projects],
            "education": [e.to_fact() for e in self.education],
            "certifications": [c.to_fact() for c in self.certifications],
            "posting_requirements_with_no_supporting_record": self.gaps,
            "skills_the_posting_wants_that_you_cannot_evidence": self.unevidenced_requests,
        }


REQUIRED_PROFILE_FIELDS = ("full_name", "email")


def build_plan(
    graph: ProfileGraph,
    job_description: str,
    *,
    company: str | None = None,
    role: str | None = None,
    max_experiences: int = 4,
    max_bullets: int = 4,
    max_projects: int = 3,
    max_skills: int = 14,
    min_relative: float = 12.0,
    keep_recent: int = 1,
    verified_only: bool = False,
) -> ResumePlan:
    experiences = graph.experiences
    if verified_only:
        experiences = [e for e in experiences if e.row.get("verified")]

    exp_matches = matching.score_records(job_description, [e.match_doc() for e in experiences])
    ach_matches = matching.score_records(
        job_description, [a.match_doc() for a in graph.all_achievements]
    )
    proj_matches = matching.score_records(job_description, [p.match_doc() for p in graph.projects])
    cert_matches = matching.score_records(
        job_description, [c.match_doc() for c in graph.certifications]
    )

    achievement_scores = {m.doc.id: m for m in ach_matches}

    # --- positions -------------------------------------------------------
    relevant = [m for m in exp_matches if m.relative >= min_relative and m.score > 0]
    chosen = relevant[:max_experiences]
    chosen_ids = {m.doc.id for m in chosen}

    # A resume that silently omits the current job reads as a gap in the
    # timeline, so the most recent positions come along even if they scored low.
    continuity_ids: set[int] = set()
    for node in experiences[:keep_recent]:
        if node.id not in chosen_ids:
            match = next((m for m in exp_matches if m.doc.id == node.id), None)
            if match:
                chosen.append(match)
                chosen_ids.add(node.id)
                continuity_ids.add(node.id)

    planned_experiences: list[PlannedExperience] = []
    for match in chosen:
        node: ExperienceNode = match.doc.payload
        ranked = sorted(
            node.achievements,
            key=lambda a: achievement_scores[a.id].score if a.id in achievement_scores else 0.0,
            reverse=True,
        )
        # Keep at least one bullet so a listed position is never a bare title.
        bullets = [a for a in ranked if achievement_scores.get(a.id, None) and achievement_scores[a.id].score > 0]
        bullets = bullets[:max_bullets] or ranked[:1]
        planned_experiences.append(
            PlannedExperience(
                node=node,
                score=match.score,
                relative=match.relative,
                bullets=bullets,
                matched_terms=match.matched_terms,
                kept_for_continuity=node.id in continuity_ids,
            )
        )

    planned_experiences.sort(
        key=lambda p: (
            p.node.row.get("is_current") or 0,
            p.node.row.get("end_date") or "9999",
            p.node.row.get("start_date") or "",
        ),
        reverse=True,
    )

    # --- projects and certifications -------------------------------------
    planned_projects = [
        PlannedProject(node=m.doc.payload, score=m.score, relative=m.relative)
        for m in proj_matches
        if m.relative >= min_relative and m.score > 0
    ][:max_projects]

    relevant_certs = [m.doc.payload for m in cert_matches if m.score > 0][:5]
    if not relevant_certs:
        relevant_certs = graph.certifications[:3]

    # --- skills ----------------------------------------------------------
    jd_weights = matching.job_description_terms(job_description)
    evidenced = graph.evidenced_skills

    scored_skills: list[tuple[float, str]] = []
    leftovers: list[str] = []
    for skill in evidenced:
        terms = matching._terms_from(str(skill["name"]))
        weight = max((jd_weights.get(t, 0.0) for t in terms), default=0.0)
        if weight > 0:
            scored_skills.append((weight * (1 + skill.get("evidence_count", 0) * 0.1), skill["name"]))
        else:
            leftovers.append(str(skill["name"]))
    scored_skills.sort(reverse=True)
    skills = [name for _, name in scored_skills][:max_skills]

    # --- what the posting wants that the record cannot support ------------
    all_docs = graph.match_docs()
    gaps = matching.coverage_gaps(job_description, all_docs, company=company)

    # `gaps` are rendered in the posting's own words, so normalise before
    # comparing them against skill names.
    evidenced_terms: set[str] = set()
    for skill in evidenced:
        evidenced_terms |= matching._terms_from(str(skill["name"]))
    unclaimable = [
        term
        for term in gaps
        if not (matching._terms_from(term) & evidenced_terms)
        and any(len(part) > 2 for part in term.split(" "))
    ]
    # Only the ones a resume could falsely claim -- named technologies and
    # credentials, not ordinary words that happen to be uncovered.
    unevidenced = matching.claimlike_terms(job_description, unclaimable)[:10]

    missing = [
        field for field in REQUIRED_PROFILE_FIELDS if not (graph.profile.get(field) or "").strip()
    ]

    return ResumePlan(
        profile=graph.profile,
        company=company,
        role=role,
        fit=matching.fit_score(job_description, all_docs),
        experiences=planned_experiences,
        projects=planned_projects,
        education=graph.education[:3],
        certifications=relevant_certs,
        skills=skills,
        other_skills=sorted(leftovers)[:20],
        gaps=gaps,
        unevidenced_requests=unevidenced,
        missing_profile_fields=missing,
    )
