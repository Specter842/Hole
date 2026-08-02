"""Send an application from your own Gmail account.

Uses the Gmail API with the narrowest scope that can send (`gmail.send`) -- it
cannot read your mail. Messages go out from your real address, one at a time,
which is why they land in an inbox instead of a promotions tab the way a bulk
transactional service would.

First run opens a browser once to authorize and caches a refresh token.

Setup:
  1. console.cloud.google.com -> new project
  2. Enable the Gmail API
  3. Credentials -> Create OAuth client ID -> Desktop app -> download the JSON
  4. Save it as gmail_credentials.json (or point dispatch.email.credentials_file at it)
"""

from __future__ import annotations

import base64
import mimetypes
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Sequence

from ..config import EmailConfig
from . import DispatchResult

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

SETUP_HELP = (
    "Gmail dispatch needs the Google client libraries:\n"
    "  pip install google-auth google-auth-oauthlib google-api-python-client"
)


class GmailError(RuntimeError):
    pass


def _load_credentials(config: EmailConfig, project_root: Path) -> Any:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise GmailError(SETUP_HELP) from exc

    token_path = project_root / config.token_file
    credentials_path = project_root / config.credentials_file

    creds = None
    if token_path.is_file():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if not credentials_path.is_file():
        raise GmailError(
            f"No OAuth client at {credentials_path}.\n"
            "Create one at console.cloud.google.com (OAuth client ID -> Desktop app), "
            "enable the Gmail API, and save the downloaded JSON there."
        )

    # Interactive, once. An unattended run cannot do this, which is why the
    # first send has to happen with you present.
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_message(
    *,
    to: str,
    subject: str,
    body: str,
    from_name: str = "",
    reply_to: str = "",
    attachments: Sequence[Path] = (),
) -> EmailMessage:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    if from_name:
        message["From"] = from_name
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)

    for path in attachments:
        path = Path(path)
        if not path.is_file():
            continue
        guessed, _ = mimetypes.guess_type(path.name)
        maintype, _, subtype = (guessed or "application/octet-stream").partition("/")
        message.add_attachment(
            path.read_bytes(),
            maintype=maintype,
            subtype=subtype or "octet-stream",
            filename=path.name,
        )
    return message


def send(
    config: EmailConfig,
    project_root: Path,
    *,
    to: str,
    subject: str,
    body: str,
    attachments: Sequence[Path] = (),
    dry_run: bool = False,
) -> DispatchResult:
    if not config.enabled:
        return DispatchResult(False, "email", "dispatch.email.enabled is false", recipient=to)
    if not to:
        return DispatchResult(False, "email", "no recipient address", recipient=None)

    message = build_message(
        to=to,
        subject=subject,
        body=body,
        from_name=config.from_name,
        reply_to=config.reply_to,
        attachments=attachments,
    )

    if dry_run:
        return DispatchResult(
            True,
            "email",
            f"dry run -- would send '{subject}' with {len(list(attachments))} attachment(s)",
            recipient=to,
        )

    try:
        from googleapiclient.discovery import build as build_service
    except ImportError as exc:
        return DispatchResult(False, "email", SETUP_HELP, recipient=to)

    try:
        creds = _load_credentials(config, project_root)
        service = build_service("gmail", "v1", credentials=creds, cache_discovery=False)
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        sent = service.users().messages().send(userId="me", body={"raw": encoded}).execute()
    except GmailError as exc:
        return DispatchResult(False, "email", str(exc), recipient=to)
    except Exception as exc:
        return DispatchResult(False, "email", f"{type(exc).__name__}: {exc}", recipient=to)

    return DispatchResult(True, "email", f"message id {sent.get('id')}", recipient=to)
