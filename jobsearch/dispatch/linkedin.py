"""LinkedIn outreach -- drafting only, permanently.

This module writes message text and builds a deep link. It does not open,
navigate, click, or submit anything on LinkedIn, and it must not be extended to.
LinkedIn's User Agreement prohibits automated access to the service and they
enforce it with restrictions and permanent bans. The account you are job-hunting
from is worth more than the clicks this would save.

Cold *email* outreach is fully automated -- see `email_gmail`. Same drafting
code, a channel that permits it.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Any

from .. import generate

CONNECTION_NOTE_LIMIT = 300  # LinkedIn's hard cap on a note attached to an invite

OUTREACH_SYSTEM_PROMPT = """You draft short, specific professional outreach messages.

You will receive a job posting, the sender's real career record, and the channel.
Write the message the sender would send.

Rules:
- Only use facts from the supplied record. Never invent employers, metrics, or skills.
- Reference one concrete, relevant accomplishment. Specificity is the entire point;
  a message that could have been sent to any company is worse than no message.
- No flattery about the company's "innovative mission". No "I hope this finds you well".
- Do not claim to have used the recipient's product unless the record says so.
- Do not invent a name for the recipient. If no name is supplied, open without one.
- Plain sentences. No em dashes, no bullet lists, no signature block.

Output format -- exactly these markers, each alone on its line:

===SUBJECT===
<one line, only for email; omit the line entirely for LinkedIn>
===MESSAGE===
<the message body>
"""


@dataclass
class OutreachDraft:
    channel: str
    subject: str
    body: str
    deep_link: str = ""
    recipient_name: str = ""

    def truncated_for_note(self) -> str:
        if len(self.body) <= CONNECTION_NOTE_LIMIT:
            return self.body
        cut = self.body[: CONNECTION_NOTE_LIMIT - 1]
        return cut[: cut.rfind(" ")] + "."


def company_people_link(company: str, role_hint: str = "") -> str:
    """A LinkedIn search URL for humans at the target company.

    This is a URL, not automation. You open it, you decide who to contact, you
    send the message yourself.
    """
    keywords = " ".join(part for part in (company, role_hint) if part).strip()
    query = urllib.parse.urlencode({"keywords": keywords, "origin": "GLOBAL_SEARCH_HEADER"})
    return f"https://www.linkedin.com/search/results/people/?{query}"


def job_search_link(title: str, location: str = "") -> str:
    query = urllib.parse.urlencode({"keywords": title, "location": location})
    return f"https://www.linkedin.com/jobs/search/?{query}"


def _parse(raw: str) -> tuple[str, str]:
    subject = ""
    body = raw.strip()
    if "===SUBJECT===" in raw:
        after = raw.split("===SUBJECT===", 1)[1]
        subject = after.split("===MESSAGE===", 1)[0].strip()
    if "===MESSAGE===" in raw:
        body = raw.split("===MESSAGE===", 1)[1].strip()
    return subject, body


def draft(
    job_description: str,
    facts: dict[str, Any],
    *,
    channel: str,
    company: str = "",
    role: str = "",
    recipient_name: str = "",
    model: str = generate.DEFAULT_MODEL,
    max_tokens: int = 1200,
) -> OutreachDraft:
    """Write one outreach message. Raises GenerationError if the API is unreachable."""
    import json

    guidance = {
        "email": "Channel: cold email. 4-6 sentences. Include a subject line.",
        "linkedin_dm": "Channel: LinkedIn direct message. 3-4 sentences, no subject line.",
        "linkedin_note": (
            f"Channel: LinkedIn connection note. Hard limit {CONNECTION_NOTE_LIMIT} "
            "characters including spaces. Two sentences. No subject line."
        ),
    }.get(channel, "Channel: short professional message.")

    recipient_line = (
        f"Recipient name: {recipient_name}" if recipient_name else "Recipient name: unknown"
    )
    message = (
        f"{guidance}\n{recipient_line}\n"
        f"Target: {role or 'the role'} at {company or 'the company'}\n\n"
        f"Job posting:\n{job_description.strip()[:6000]}\n\n"
        f"Sender's career record (the complete set of usable facts):\n"
        f"{json.dumps(facts, indent=2, ensure_ascii=False)}"
    )

    raw, _usage = generate.call_model(
        OUTREACH_SYSTEM_PROMPT, message, model=model, max_tokens=max_tokens
    )
    subject, body = _parse(raw)

    if channel == "linkedin_note":
        deep_link = company_people_link(company, role)
    elif channel == "linkedin_dm":
        deep_link = company_people_link(company)
    else:
        deep_link = ""

    result = OutreachDraft(
        channel=channel,
        subject=subject,
        body=body,
        deep_link=deep_link,
        recipient_name=recipient_name,
    )
    if channel == "linkedin_note":
        result.body = result.truncated_for_note()
    return result
