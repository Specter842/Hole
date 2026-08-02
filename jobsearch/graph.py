"""In-memory read model of the profile graph.

Loads the whole profile once and hands out `MatchDoc`s for the matcher. The
important structural fact: an experience's match document absorbs the text of
its own accomplishments, so a position ranks highly because of what was done
there, not just because of its job title.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field as dc_field
from typing import Any, Iterable, Sequence

from . import db
from .matching import MatchDoc


def date_range(start: str | None, end: str | None, *, is_current: bool = False) -> str:
    if not start and not end:
        return ""
    if is_current or (start and not end):
        return f"{start} - Present"
    if end and not start:
        return str(end)
    return f"{start} - {end}"


def _clean(*parts: Any) -> str:
    return " ".join(str(p) for p in parts if p)


@dataclass
class AchievementNode:
    row: dict[str, Any]
    skills: list[str] = dc_field(default_factory=list)
    parent_kind: str = ""
    parent_id: int = 0
    parent_label: str = ""
    parent_field: str | None = None

    @property
    def id(self) -> int:
        return int(self.row["id"])

    @property
    def title(self) -> str:
        return str(self.row.get("title") or "")

    @property
    def verified(self) -> bool:
        return bool(self.row.get("verified"))

    def match_doc(self) -> MatchDoc:
        return MatchDoc(
            key=("achievement", self.id),
            label=f"{self.title} ({self.parent_label})" if self.parent_label else self.title,
            fields={
                "tags": self.skills,
                "title": self.title,
                "field": self.parent_field,
                "impact": self.row.get("quantified_impact"),
                "organization": self.parent_label,
                "text": self.row.get("description"),
            },
            payload=self,
        )

    def to_fact(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.row.get("description"),
            "quantified_impact": self.row.get("quantified_impact"),
            "skills": self.skills,
            "verified": self.verified,
        }


@dataclass
class ExperienceNode:
    row: dict[str, Any]
    achievements: list[AchievementNode] = dc_field(default_factory=list)
    skills: list[str] = dc_field(default_factory=list)

    @property
    def id(self) -> int:
        return int(self.row["id"])

    @property
    def title(self) -> str:
        return str(self.row.get("title") or "")

    @property
    def organization(self) -> str:
        return str(self.row.get("organization") or "")

    @property
    def dates(self) -> str:
        return date_range(
            self.row.get("start_date"),
            self.row.get("end_date"),
            is_current=bool(self.row.get("is_current")),
        )

    @property
    def label(self) -> str:
        return _clean(self.title, "@", self.organization) if self.organization else self.title

    def match_doc(self) -> MatchDoc:
        bullet_text = " . ".join(
            _clean(a.title, a.row.get("description"), a.row.get("quantified_impact"))
            for a in self.achievements
        )
        return MatchDoc(
            key=("experience", self.id),
            label=self.label,
            fields={
                "tags": self.skills,
                "title": self.title,
                "field": self.row.get("field"),
                "organization": self.organization,
                "text": _clean(self.row.get("description"), bullet_text),
            },
            payload=self,
        )

    def to_fact(self, achievements: Sequence[AchievementNode] | None = None) -> dict[str, Any]:
        chosen = list(achievements if achievements is not None else self.achievements)
        return {
            "id": self.id,
            "title": self.title,
            "organization": self.organization,
            "employment_type": self.row.get("employment_type"),
            "location": self.row.get("location"),
            "dates": self.dates,
            "start_date": self.row.get("start_date"),
            "end_date": self.row.get("end_date"),
            "is_current": bool(self.row.get("is_current")),
            "description": self.row.get("description"),
            "skills": self.skills,
            "accomplishments": [a.to_fact() for a in chosen],
        }


@dataclass
class ProjectNode:
    row: dict[str, Any]
    achievements: list[AchievementNode] = dc_field(default_factory=list)
    skills: list[str] = dc_field(default_factory=list)

    @property
    def id(self) -> int:
        return int(self.row["id"])

    @property
    def name(self) -> str:
        return str(self.row.get("name") or "")

    @property
    def dates(self) -> str:
        return date_range(self.row.get("start_date"), self.row.get("end_date"))

    def match_doc(self) -> MatchDoc:
        bullet_text = " . ".join(
            _clean(a.title, a.row.get("description")) for a in self.achievements
        )
        return MatchDoc(
            key=("project", self.id),
            label=self.name,
            fields={
                "tags": self.skills,
                "title": self.name,
                "field": self.row.get("field"),
                "organization": self.row.get("organization"),
                "text": _clean(self.row.get("description"), self.row.get("role"), bullet_text),
            },
            payload=self,
        )

    def to_fact(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.row.get("role"),
            "description": self.row.get("description"),
            "url": self.row.get("url"),
            "dates": self.dates,
            "skills": self.skills,
            "accomplishments": [a.to_fact() for a in self.achievements],
        }


@dataclass
class EducationNode:
    row: dict[str, Any]
    achievements: list[AchievementNode] = dc_field(default_factory=list)
    skills: list[str] = dc_field(default_factory=list)

    @property
    def id(self) -> int:
        return int(self.row["id"])

    @property
    def label(self) -> str:
        degree = _clean(self.row.get("degree"), self.row.get("field_of_study"))
        return _clean(degree, "-", self.row.get("organization")) if degree else str(
            self.row.get("organization") or ""
        )

    @property
    def dates(self) -> str:
        return date_range(self.row.get("start_date"), self.row.get("end_date"))

    def match_doc(self) -> MatchDoc:
        return MatchDoc(
            key=("education", self.id),
            label=self.label,
            fields={
                "tags": self.skills,
                "title": _clean(self.row.get("degree"), self.row.get("field_of_study")),
                "organization": self.row.get("organization"),
                "text": _clean(self.row.get("description"), self.row.get("activities")),
            },
            payload=self,
        )

    def to_fact(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "school": self.row.get("organization"),
            "degree": self.row.get("degree"),
            "field_of_study": self.row.get("field_of_study"),
            "dates": self.dates,
            "grade": self.row.get("grade"),
            "activities": self.row.get("activities"),
        }


@dataclass
class SimpleNode:
    """Certifications, awards, publications -- flat records with no children."""

    kind: str
    row: dict[str, Any]
    title_key: str
    org_key: str | None = None

    @property
    def id(self) -> int:
        return int(self.row["id"])

    @property
    def label(self) -> str:
        return str(self.row.get(self.title_key) or "")

    def match_doc(self) -> MatchDoc:
        return MatchDoc(
            key=(self.kind, self.id),
            label=self.label,
            fields={
                "title": self.label,
                "organization": self.row.get(self.org_key) if self.org_key else None,
                "text": self.row.get("description"),
            },
            payload=self,
        )

    def to_fact(self) -> dict[str, Any]:
        return {k: v for k, v in self.row.items() if v is not None and k != "source_id"}


@dataclass
class ProfileGraph:
    profile: dict[str, Any] = dc_field(default_factory=dict)
    experiences: list[ExperienceNode] = dc_field(default_factory=list)
    projects: list[ProjectNode] = dc_field(default_factory=list)
    education: list[EducationNode] = dc_field(default_factory=list)
    certifications: list[SimpleNode] = dc_field(default_factory=list)
    awards: list[SimpleNode] = dc_field(default_factory=list)
    publications: list[SimpleNode] = dc_field(default_factory=list)
    skills: list[dict[str, Any]] = dc_field(default_factory=list)
    languages: list[dict[str, Any]] = dc_field(default_factory=list)
    recommendations: list[dict[str, Any]] = dc_field(default_factory=list)

    # ------------------------------------------------------------------ views

    @property
    def all_achievements(self) -> list[AchievementNode]:
        out: list[AchievementNode] = []
        for parent in (*self.experiences, *self.projects, *self.education):
            out.extend(parent.achievements)
        return out

    @property
    def evidenced_skills(self) -> list[dict[str, Any]]:
        """Only skills some record actually demonstrates."""
        return [s for s in self.skills if s.get("evidence_count", 0) > 0]

    def is_empty(self) -> bool:
        return not (self.experiences or self.projects or self.education)

    def counts(self) -> dict[str, int]:
        return {
            "experiences": len(self.experiences),
            "accomplishments": len(self.all_achievements),
            "projects": len(self.projects),
            "education": len(self.education),
            "skills": len(self.skills),
            "evidenced_skills": len(self.evidenced_skills),
            "certifications": len(self.certifications),
        }

    # ------------------------------------------------------------------ matching

    def match_docs(self, kinds: Iterable[str] | None = None) -> list[MatchDoc]:
        wanted = set(kinds) if kinds else None
        docs: list[MatchDoc] = []

        def maybe(kind: str, items: Iterable[Any]) -> None:
            if wanted is not None and kind not in wanted:
                return
            docs.extend(item.match_doc() for item in items)

        maybe("experience", self.experiences)
        maybe("achievement", self.all_achievements)
        maybe("project", self.projects)
        maybe("education", self.education)
        maybe("certification", self.certifications)
        maybe("award", self.awards)
        maybe("publication", self.publications)
        return docs

    # ------------------------------------------------------------------ loading

    @classmethod
    def load(cls, conn: sqlite3.Connection) -> "ProfileGraph":
        skill_names = {
            int(r["id"]): str(r["name"]) for r in conn.execute("SELECT id, name FROM skills")
        }

        def skills_for(column: str) -> dict[int, list[str]]:
            mapping: dict[int, list[str]] = {}
            for row in conn.execute(
                f"SELECT {column} AS target, skill_id FROM skill_evidence WHERE {column} IS NOT NULL"
            ):
                name = skill_names.get(int(row["skill_id"]))
                if not name:
                    continue
                mapping.setdefault(int(row["target"]), []).append(name)
            return {k: sorted(set(v)) for k, v in mapping.items()}

        by_experience = skills_for("experience_id")
        by_project = skills_for("project_id")
        by_education = skills_for("education_id")
        by_achievement = skills_for("achievement_id")

        experiences: list[ExperienceNode] = []
        for row in db.list_experiences(conn):
            experiences.append(
                ExperienceNode(row=row, skills=by_experience.get(int(row["id"]), []))
            )
        projects = [
            ProjectNode(row=row, skills=by_project.get(int(row["id"]), []))
            for row in db.list_projects(conn)
        ]
        education = [
            EducationNode(row=row, skills=by_education.get(int(row["id"]), []))
            for row in db.list_education(conn)
        ]

        parents: dict[tuple[str, int], Any] = {}
        for node in experiences:
            parents[("experience", node.id)] = node
        for node in projects:
            parents[("project", node.id)] = node
        for node in education:
            parents[("education", node.id)] = node

        for row in db.list_achievements(conn):
            for kind, column in (
                ("experience", "experience_id"),
                ("project", "project_id"),
                ("education", "education_id"),
            ):
                parent_id = row.get(column)
                if not parent_id:
                    continue
                parent = parents.get((kind, int(parent_id)))
                if parent is None:
                    continue
                label = getattr(parent, "label", None) or getattr(parent, "name", "")
                node = AchievementNode(
                    row=row,
                    skills=by_achievement.get(int(row["id"]), []),
                    parent_kind=kind,
                    parent_id=int(parent_id),
                    parent_label=str(label),
                    parent_field=parent.row.get("field"),
                )
                parent.achievements.append(node)
                break

        return cls(
            profile=db.get_profile(conn),
            experiences=experiences,
            projects=projects,
            education=education,
            certifications=[
                SimpleNode("certification", row, "name", "issuer")
                for row in db.list_table(conn, "certifications")
            ],
            awards=[SimpleNode("award", row, "name", "issuer") for row in db.list_table(conn, "awards")],
            publications=[
                SimpleNode("publication", row, "title", "publisher")
                for row in db.list_table(conn, "publications")
            ],
            skills=db.list_skills(conn),
            languages=db.list_table(conn, "languages"),
            recommendations=db.list_table(conn, "recommendations"),
        )
