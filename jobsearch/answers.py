"""Standing answers to the questions application forms ask.

A resume says where someone worked. It does not say whether they need visa
sponsorship, what their notice period is, or why they want this particular job.
Those questions block every real ATS form, and the tool refuses to invent
answers to them -- correctly, since an invented "no" to a sponsorship question
is a lie told to an employer under the candidate's name.

So they get stored instead. The candidate writes each answer once, verbatim,
and filling a form becomes a lookup. That keeps auto-submit inside the same rule
as the rest of the system: everything sent traces to something a human recorded.

Matching is deliberately conservative. A stored answer is used only when its
pattern actually appears in the question, longest pattern first, so a specific
answer beats a general one. Anything unmatched stops the run -- a wrong answer
is worse than an unfinished form.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Sequence

from . import db

# Question labels arrive with markers, colons, and stray whitespace around them.
_TRIM = re.compile(r"[*:?••]+")
_SPACE = re.compile(r"\s+")

# Answers to these are never stored or filled, whatever is in the table. They are
# the questions an employer must not receive a machine-generated answer to, and
# the ones a candidate is entitled to decline without it looking like an evasion.
PROTECTED = re.compile(
    r"(gender|race|ethnic|veteran|disab|sexual orientation|pronoun|"
    r"self.?identif|voluntary|hispanic)",
    re.IGNORECASE,
)

KINDS = ("text", "choice", "boolean")


@dataclass
class Answer:
    id: int
    pattern: str
    answer: str
    kind: str = "text"
    company: str | None = None
    notes: str | None = None

    @property
    def scoped(self) -> bool:
        return bool(self.company)


def normalize(question: str) -> str:
    """Lowercased, punctuation-stripped form used for matching on both sides."""
    text = _TRIM.sub(" ", str(question or "").lower())
    return _SPACE.sub(" ", text).strip()


def _row_to_answer(row: sqlite3.Row | dict[str, Any]) -> Answer:
    data = dict(row)
    return Answer(
        id=int(data["id"]),
        pattern=str(data["pattern"]),
        answer=str(data["answer"]),
        kind=str(data.get("kind") or "text"),
        company=data.get("company"),
        notes=data.get("notes"),
    )


# --------------------------------------------------------------------------- storage


def add(
    conn: sqlite3.Connection,
    pattern: str,
    answer: str,
    *,
    kind: str = "text",
    company: str | None = None,
    notes: str | None = None,
) -> int:
    pattern = normalize(pattern)
    if not pattern:
        raise ValueError("An answer needs a question pattern to match against.")
    if not str(answer).strip():
        raise ValueError("An empty answer would submit a blank field.")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of: {', '.join(KINDS)}")
    if PROTECTED.search(pattern):
        raise ValueError(
            "That looks like a demographic or voluntary self-identification question. "
            "This tool never fills those in -- answer them yourself, or leave them blank."
        )
    existing = conn.execute(
        "SELECT id FROM application_answers WHERE pattern = ? AND IFNULL(company,'') = ?",
        (pattern, company or ""),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE application_answers SET answer = ?, kind = ?, notes = ?, updated_at = ? "
            "WHERE id = ?",
            (answer, kind, notes, db.now(), existing["id"]),
        )
        return int(existing["id"])
    return db.insert_row(
        conn,
        "application_answers",
        {
            "pattern": pattern,
            "answer": answer,
            "kind": kind,
            "company": company,
            "notes": notes,
            "created_at": db.now(),
        },
    )


def list_all(conn: sqlite3.Connection, *, company: str | None = None) -> list[Answer]:
    """Every stored answer. With `company`, everything usable for that employer.

    Note this is the *listing* view -- `company=None` shows the whole table,
    including answers scoped to a single employer, because that is what someone
    running `answers list` wants to see. Matching uses `candidates()`, which is
    stricter.
    """
    if company:
        rows = conn.execute(
            "SELECT * FROM application_answers "
            "WHERE company IS NULL OR company = '' OR company = ? "
            "ORDER BY LENGTH(pattern) DESC",
            (company,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM application_answers ORDER BY LENGTH(pattern) DESC"
        ).fetchall()
    return [_row_to_answer(r) for r in rows]


def candidates(conn: sqlite3.Connection, company: str | None) -> list[Answer]:
    """Answers eligible to fill a form for `company`.

    Without a company, only unscoped answers qualify. An answer written for
    Anthropic must never end up on Figma's form -- that is the whole point of
    scoping it, and it is the kind of mistake nobody notices until an employer
    reads it.
    """
    if company:
        return list_all(conn, company=company)
    rows = conn.execute(
        "SELECT * FROM application_answers WHERE company IS NULL OR company = '' "
        "ORDER BY LENGTH(pattern) DESC"
    ).fetchall()
    return [_row_to_answer(r) for r in rows]


def remove(conn: sqlite3.Connection, answer_id: int) -> bool:
    return db.delete_row(conn, "application_answers", answer_id)


# --------------------------------------------------------------------------- matching


def find(
    conn: sqlite3.Connection, question: str, *, company: str | None = None
) -> Answer | None:
    """The stored answer covering `question`, or None.

    Company-scoped answers win over general ones, and among equals the longest
    pattern wins -- "do you require visa sponsorship" should beat "visa".
    """
    if PROTECTED.search(question or ""):
        return None
    target = normalize(question)
    if not target:
        return None
    best: Answer | None = None
    for candidate in candidates(conn, company):
        if candidate.pattern not in target:
            continue
        if best is None:
            best = candidate
            continue
        # Prefer a company-scoped answer, then the more specific pattern.
        if candidate.scoped and not best.scoped:
            best = candidate
        elif candidate.scoped == best.scoped and len(candidate.pattern) > len(best.pattern):
            best = candidate
    return best


def resolve(
    conn: sqlite3.Connection, questions: Sequence[str], *, company: str | None = None
) -> tuple[dict[str, Answer], list[str]]:
    """Split `questions` into the ones we can answer and the ones we cannot."""
    matched: dict[str, Answer] = {}
    unmatched: list[str] = []
    for question in questions:
        found = find(conn, question, company=company)
        if found:
            matched[question] = found
        else:
            unmatched.append(question)
    return matched, unmatched


# --------------------------------------------------------------------------- gaps


def record_gap(
    conn: sqlite3.Connection,
    question: str,
    *,
    company: str | None = None,
    job_id: int | None = None,
) -> None:
    """Remember a question nothing covered, so `answers gaps` can show it later."""
    question = str(question or "").strip()
    if not question or PROTECTED.search(question):
        return
    # Empty string, never NULL. SQLite treats NULLs as distinct in a UNIQUE
    # constraint, so a nullable `company` would silently insert a fresh row on
    # every repeat instead of incrementing the count -- and the whole value of
    # this table is knowing which questions block you most often.
    conn.execute(
        "INSERT INTO unanswered_questions(question, company, job_id, last_seen) "
        "VALUES(?, ?, ?, ?) "
        "ON CONFLICT(question, company) DO UPDATE SET "
        "  seen_count = seen_count + 1, last_seen = excluded.last_seen",
        (question, company or "", job_id, db.now()),
    )


def gaps(conn: sqlite3.Connection, *, limit: int = 50) -> list[dict[str, Any]]:
    """Unanswered questions, most frequently asked first."""
    rows = conn.execute(
        "SELECT question, company, seen_count, last_seen FROM unanswered_questions "
        "ORDER BY seen_count DESC, last_seen DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return db.rows_to_dicts(rows)


def clear_gap(conn: sqlite3.Connection, question: str) -> int:
    cursor = conn.execute(
        "DELETE FROM unanswered_questions WHERE question = ?", (question,)
    )
    return cursor.rowcount


def prune_answered(conn: sqlite3.Connection) -> int:
    """Drop recorded gaps that a stored answer now covers."""
    removed = 0
    for row in list(gaps(conn, limit=1000)):
        if find(conn, row["question"], company=row.get("company")):
            removed += clear_gap(conn, row["question"])
    return removed
