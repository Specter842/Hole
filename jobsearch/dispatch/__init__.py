"""Getting an approved application out the door.

Three channels, with very different levels of automation, for reasons that are
about the rules of each platform rather than difficulty:

- `email_gmail`  fully automated. Your own Gmail account, your own address,
                 OAuth, one message at a time. Nothing about this is against
                 anyone's terms.
- `ats_form`     fully automated. Greenhouse/Lever/Ashby application forms
                 driven in a real browser. Aborts on anything it cannot fill
                 honestly, and never touches a CAPTCHA.
- `linkedin`     draft only, permanently. Writes the message and hands you a
                 deep link. LinkedIn's User Agreement bans automated access and
                 enforces it with account restrictions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Addresses that appear in postings but are not where applications go.
NON_APPLY_ADDRESSES = re.compile(
    r"(noreply|no-reply|donotreply|privacy|legal|press|support|security|abuse)@", re.IGNORECASE
)


@dataclass
class DispatchResult:
    ok: bool
    channel: str
    detail: str = ""
    recipient: str | None = None
    artifacts: list[str] = field(default_factory=list)
    # Required questions the form asked that nothing could answer. Reported
    # rather than swallowed so the caller can record them and the candidate can
    # write the answer once instead of hitting the same wall on every posting.
    unanswered: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        status = "sent" if self.ok else "failed"
        target = f" -> {self.recipient}" if self.recipient else ""
        return f"[{self.channel}] {status}{target}: {self.detail}"


def find_apply_email(*texts: str | None) -> str | None:
    """An address the posting itself invites applications to.

    Guessing careers@<domain> would be spam. This only returns something when
    the employer wrote an address down, which is an explicit invitation.
    """
    for text in texts:
        if not text:
            continue
        for match in EMAIL_RE.finditer(text):
            address = match.group(0).rstrip(".,;)")
            if NON_APPLY_ADDRESSES.search(address):
                continue
            if address.lower().endswith((".png", ".jpg", ".gif")):
                continue
            return address
    return None


def summarize(results: list[DispatchResult]) -> dict[str, Any]:
    return {
        "sent": sum(1 for r in results if r.ok),
        "failed": sum(1 for r in results if not r.ok),
        "by_channel": {
            channel: sum(1 for r in results if r.channel == channel and r.ok)
            for channel in {r.channel for r in results}
        },
    }
