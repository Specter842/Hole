"""Resume + cover letter generation via the Anthropic API.

The model is given nothing but the profile row and the achievements the matcher
selected. It is told, in the system prompt and again in the payload, that it may
not add facts. `verify.py` then checks the output against those same facts.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .db import PROJECT_ROOT

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 4000

RESUME_MARKER = "===RESUME==="
LETTER_MARKER = "===COVER_LETTER==="
NOTES_MARKER = "===FIT_NOTES==="

SYSTEM_PROMPT = """You are a resume-tailoring assistant.
You will receive a job description and a plan drawn from the candidate's real career
record. Generate a tailored one-page resume and a cover letter.

Rules:
- Only use facts given below. Never invent employers, dates, metrics, or skills.
- If the record doesn't strongly match the role, say so plainly instead of stretching
  the truth.

How to read the plan:
- `experience` is already filtered and ordered for this posting. Each entry carries its
  own `accomplishments`; write those as the bullets under that employer, and do not move
  an accomplishment to a different employer.
- `skills_you_may_claim` is a closed list -- every entry is backed by a record in the
  candidate's history. `other_evidenced_skills` are real but less relevant; use them only
  if they genuinely fit.
- `skills_the_posting_wants_that_you_cannot_evidence` is exactly what it says. Never
  claim any of it. Report it in FIT_NOTES.

Additional constraints:
- Every line you write must trace back to a supplied record or to the candidate profile
  block. Rephrasing for tone is fine; adding information is not.
- Do not introduce numbers, percentages, dollar figures, team sizes, or durations that
  are not present in the supplied data.
- Do not claim a skill outside the two skills lists, no matter how central it is to the
  posting.
- Do not invent a job title, a date range, or a company that is not in `experience`.
- Never emit placeholders such as [Your Name], [Company], [Address], or TODO. If a detail
  you would normally include is missing from the profile, leave it out of the documents
  and name it under FIT_NOTES as missing.
- Do not invent the hiring manager's name. Address the letter to the team or company.
- The resume must fit one page: a header built from the profile, a short summary, a
  skills line, then Experience with each position's accomplishments as bullets, then
  Projects / Education / Certifications only if the plan supplies them.
- Cover letter: 3-4 short paragraphs, specific, no boilerplate enthusiasm, no restating
  the resume line by line.

Output format. Return exactly these three sections, each marker alone on its own line,
in this order, with nothing before the first marker:

===RESUME===
<the resume, markdown>
===COVER_LETTER===
<the cover letter, markdown>
===FIT_NOTES===
<blunt assessment for the candidate's eyes only: how well the real record fits this
posting, which posting requirements are not evidenced by any supplied achievement, any
profile fields that were missing, and a recommendation to apply or skip. Never send this
section to an employer.>
"""


class GenerationError(RuntimeError):
    pass


@dataclass
class TailoredOutput:
    resume: str
    cover_letter: str
    fit_notes: str
    raw: str
    model: str
    usage: dict[str, Any]

    def is_complete(self) -> bool:
        return bool(self.resume.strip() and self.cover_letter.strip())


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env support so the API key doesn't have to live in the shell profile."""
    env_path = path or (PROJECT_ROOT / ".env")
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def build_user_message(job_description: str, facts: dict[str, Any]) -> str:
    facts_json = json.dumps(facts, indent=2, ensure_ascii=False)
    return (
        f"Job description:\n{job_description.strip()}\n\n"
        f"Career record plan:\n{facts_json}\n\n"
        "The JSON above is the complete set of facts you may use. Anything absent from it "
        "does not exist for the purposes of these documents."
    )


def _extract_section(text: str, start: str, *stops: str) -> str:
    idx = text.find(start)
    if idx == -1:
        return ""
    body = text[idx + len(start):]
    cut = len(body)
    for stop in stops:
        found = body.find(stop)
        if found != -1:
            cut = min(cut, found)
    return body[:cut].strip()


def parse_response(text: str) -> tuple[str, str, str]:
    resume = _extract_section(text, RESUME_MARKER, LETTER_MARKER, NOTES_MARKER)
    letter = _extract_section(text, LETTER_MARKER, NOTES_MARKER)
    notes = _extract_section(text, NOTES_MARKER)
    if not resume and not letter:
        # Model ignored the format; keep everything rather than silently dropping it.
        return text.strip(), "", ""
    return resume, letter, notes


def call_model(
    system_prompt: str,
    user_message: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> tuple[str, dict[str, Any]]:
    """One Anthropic call. Shared by tailoring and by document ingestion."""
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise GenerationError(
            "ANTHROPIC_API_KEY is not set.\n"
            "  PowerShell (this session): $env:ANTHROPIC_API_KEY = 'sk-ant-...'\n"
            "  Or create a .env file next to jobsearch.db containing ANTHROPIC_API_KEY=sk-ant-..."
        )
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - environment problem, not logic
        raise GenerationError("The anthropic SDK is not installed. Run: pip install anthropic") from exc

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as exc:  # SDK raises a family of API errors; surface them plainly
        raise GenerationError(f"Anthropic API call failed: {type(exc).__name__}: {exc}") from exc

    text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    usage = {
        "input_tokens": getattr(response.usage, "input_tokens", None),
        "output_tokens": getattr(response.usage, "output_tokens", None),
        "stop_reason": getattr(response, "stop_reason", None),
    }
    return text, usage


def generate(
    job_description: str,
    plan: Any,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> TailoredOutput:
    """Render a ResumePlan into documents. The plan decides what is true."""
    if plan.is_empty():
        raise GenerationError(
            "Nothing in the profile matched this posting. Nothing can be written without "
            "facts to write from -- add relevant experience, or lower --min-score."
        )

    raw, usage = call_model(
        SYSTEM_PROMPT,
        build_user_message(job_description, plan.to_facts()),
        model=model,
        max_tokens=max_tokens,
    )
    resume, letter, notes = parse_response(raw)
    return TailoredOutput(
        resume=resume,
        cover_letter=letter,
        fit_notes=notes,
        raw=raw,
        model=model,
        usage=usage,
    )


def slugify(value: str | None, fallback: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or fallback
