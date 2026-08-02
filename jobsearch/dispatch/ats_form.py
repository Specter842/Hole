"""Fill and submit Greenhouse / Lever / Ashby application forms in a real browser.

Needs Playwright:

    pip install playwright
    playwright install chromium

Design constraints, all of which mean "stop rather than guess":

- It fills only fields it recognizes. A required field it cannot map is an abort,
  not a blank submission or an invented answer.
- It never attempts a CAPTCHA. If one is present the run stops and the
  application goes to the review queue for you to finish by hand.
- It screenshots the completed form before submitting, so every unattended
  submission has an artifact you can look at afterwards.
- Demographic and voluntary self-identification questions are left untouched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import AtsConfig
from . import DispatchResult

SETUP_HELP = (
    "ATS form submission needs Playwright:\n"
    "  pip install playwright\n"
    "  playwright install chromium"
)

CAPTCHA_MARKERS = (
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    ".g-recaptcha",
    "#cf-challenge-running",
    "[data-sitekey]",
)

# Questions we deliberately never answer on someone's behalf.
SKIP_LABEL_PATTERNS = re.compile(
    r"(gender|race|ethnic|veteran|disability|sexual orientation|pronoun|"
    r"self.?identif|voluntary|hispanic|salary expectation|desired compensation)",
    re.IGNORECASE,
)


@dataclass
class ApplicantFields:
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    website: str = ""
    github: str = ""
    location: str = ""
    resume_path: Path | None = None
    cover_letter_text: str = ""

    @classmethod
    def from_profile(cls, profile: dict[str, Any], resume_path: Path | None = None,
                     cover_letter_text: str = "") -> "ApplicantFields":
        full_name = str(profile.get("full_name") or "").strip()
        first, _, last = full_name.partition(" ")
        return cls(
            first_name=first,
            last_name=last or first,
            full_name=full_name,
            email=str(profile.get("email") or ""),
            phone=str(profile.get("phone") or ""),
            linkedin=str(profile.get("linkedin_url") or ""),
            website=str(profile.get("website") or ""),
            github=str(profile.get("github") or ""),
            location=str(profile.get("location") or ""),
            resume_path=resume_path,
            cover_letter_text=cover_letter_text,
        )

    def missing_required(self) -> list[str]:
        missing = [
            name
            for name, value in (
                ("full_name", self.full_name),
                ("email", self.email),
            )
            if not value
        ]
        if not self.resume_path or not Path(self.resume_path).is_file():
            missing.append("resume file")
        return missing


def detect_ats(url: str) -> str:
    lowered = (url or "").lower()
    if "greenhouse.io" in lowered:
        return "greenhouse"
    if "lever.co" in lowered:
        return "lever"
    if "ashbyhq.com" in lowered:
        return "ashby"
    return "unknown"


# Ordered (selector, attribute-of-ApplicantFields) pairs per ATS. The first
# selector that resolves to exactly one visible element wins.
FIELD_MAP: dict[str, list[tuple[str, str]]] = {
    "greenhouse": [
        ("#first_name", "first_name"),
        ("#last_name", "last_name"),
        ("#email", "email"),
        ("#phone", "phone"),
        ("input[name='job_application[answers_attributes][0][text_value]']", "linkedin"),
    ],
    "lever": [
        ("input[name='name']", "full_name"),
        ("input[name='email']", "email"),
        ("input[name='phone']", "phone"),
        ("input[name='urls[LinkedIn]']", "linkedin"),
        ("input[name='urls[GitHub]']", "github"),
        ("input[name='org']", "location"),
    ],
    "ashby": [
        ("input[name='_systemfield_name']", "full_name"),
        ("input[name='_systemfield_email']", "email"),
        ("input[name='_systemfield_phone']", "phone"),
    ],
}

RESUME_SELECTORS = {
    "greenhouse": ["#resume", "input[type='file'][name*='resume']"],
    "lever": ["input[name='resume']", "input[type='file']"],
    "ashby": ["input[type='file']"],
}

COVER_LETTER_SELECTORS = {
    "greenhouse": ["#cover_letter_text", "textarea[name*='cover_letter']"],
    "lever": ["textarea[name='comments']"],
    "ashby": ["textarea"],
}

SUBMIT_SELECTORS = {
    "greenhouse": ["#submit_app", "input[type='submit']", "button[type='submit']"],
    "lever": [".template-btn-submit", "button[type='submit']"],
    "ashby": ["button[type='submit']"],
}


def _fill_first(page: Any, selectors: list[str], value: str) -> bool:
    if not value:
        return False
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() >= 1 and locator.first.is_visible():
                locator.first.fill(value)
                return True
        except Exception:
            continue
    return False


def _has_captcha(page: Any) -> bool:
    for marker in CAPTCHA_MARKERS:
        try:
            if page.locator(marker).count() > 0:
                return True
        except Exception:
            continue
    return False


def _unfilled_required(page: Any) -> list[str]:
    """Required inputs still empty after our pass, excluding ones we won't answer."""
    try:
        return page.evaluate(
            """() => {
                const skip = /gender|race|ethnic|veteran|disability|orientation|pronoun|self.?identif|voluntary|hispanic/i;
                const out = [];
                for (const el of document.querySelectorAll('input[required], select[required], textarea[required]')) {
                    if (el.type === 'hidden' || el.disabled) continue;
                    const label = (el.labels && el.labels[0] ? el.labels[0].innerText : '')
                                  || el.getAttribute('aria-label') || el.name || el.id || '(unnamed)';
                    if (skip.test(label)) continue;
                    const empty = el.type === 'file' ? el.files.length === 0 : !el.value;
                    if (empty) out.push(label.trim().slice(0, 60));
                }
                return out;
            }"""
        )
    except Exception:
        return []


def submit(
    config: AtsConfig,
    *,
    apply_url: str,
    fields: ApplicantFields,
    project_root: Path,
    slug: str,
    dry_run: bool = False,
) -> DispatchResult:
    if not config.enabled:
        return DispatchResult(False, "ats_form", "dispatch.ats.enabled is false")

    ats = detect_ats(apply_url)
    if ats == "unknown":
        return DispatchResult(False, "ats_form", f"unrecognized application host: {apply_url}")

    missing = fields.missing_required()
    if missing:
        return DispatchResult(False, "ats_form", f"cannot fill the form: missing {', '.join(missing)}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return DispatchResult(False, "ats_form", SETUP_HELP)

    shot_dir = project_root / config.screenshot_dir
    shot_dir.mkdir(parents=True, exist_ok=True)
    screenshot = shot_dir / f"{slug}.png"
    artifacts: list[str] = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=config.headless)
            context = browser.new_context(accept_downloads=False)
            page = context.new_page()
            page.set_default_timeout(config.timeout_seconds * 1000)
            page.goto(apply_url, wait_until="domcontentloaded")

            if _has_captcha(page):
                page.screenshot(path=str(screenshot), full_page=True)
                browser.close()
                return DispatchResult(
                    False,
                    "ats_form",
                    "a CAPTCHA is present -- stopping. Finish this one by hand.",
                    artifacts=[str(screenshot)],
                )

            filled: list[str] = []
            for selector, attribute in FIELD_MAP.get(ats, []):
                if _fill_first(page, [selector], getattr(fields, attribute, "")):
                    filled.append(attribute)

            if fields.resume_path:
                for selector in RESUME_SELECTORS.get(ats, []):
                    try:
                        locator = page.locator(selector)
                        if locator.count() >= 1:
                            locator.first.set_input_files(str(fields.resume_path))
                            filled.append("resume")
                            break
                    except Exception:
                        continue

            if fields.cover_letter_text:
                if _fill_first(page, COVER_LETTER_SELECTORS.get(ats, []), fields.cover_letter_text):
                    filled.append("cover_letter")

            page.screenshot(path=str(screenshot), full_page=True)
            artifacts.append(str(screenshot))

            outstanding = _unfilled_required(page)
            if outstanding:
                browser.close()
                return DispatchResult(
                    False,
                    "ats_form",
                    "required field(s) this tool will not guess at: " + ", ".join(outstanding[:6]),
                    artifacts=artifacts,
                )

            if dry_run:
                browser.close()
                return DispatchResult(
                    True,
                    "ats_form",
                    f"dry run -- filled {', '.join(filled)}, stopped before submit",
                    artifacts=artifacts,
                )

            submitted = False
            for selector in SUBMIT_SELECTORS.get(ats, []):
                try:
                    locator = page.locator(selector)
                    if locator.count() >= 1 and locator.first.is_visible():
                        locator.first.click()
                        submitted = True
                        break
                except Exception:
                    continue

            if not submitted:
                browser.close()
                return DispatchResult(False, "ats_form", "could not find a submit button", artifacts=artifacts)

            page.wait_for_load_state("networkidle", timeout=config.timeout_seconds * 1000)
            confirmation = shot_dir / f"{slug}_confirmation.png"
            page.screenshot(path=str(confirmation), full_page=True)
            artifacts.append(str(confirmation))

            body = (page.content() or "").lower()
            browser.close()

            looks_confirmed = any(
                marker in body
                for marker in ("thank you", "application received", "we have received", "submitted")
            )
            return DispatchResult(
                looks_confirmed,
                "ats_form",
                "submitted and confirmation page matched"
                if looks_confirmed
                else "submitted, but no confirmation text found -- check the screenshot",
                artifacts=artifacts,
            )
    except Exception as exc:
        return DispatchResult(
            False, "ats_form", f"{type(exc).__name__}: {exc}", artifacts=artifacts
        )
