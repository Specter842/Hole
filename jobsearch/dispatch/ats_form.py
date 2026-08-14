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
from typing import Any, Callable

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

# Fallback for anything the selectors above miss. Greenhouse's current React
# board is the case that forced this: `#first_name` still resolves to a legacy
# element while the input the applicant actually types into is a sibling with no
# id, no name, and `aria-required` instead of `required`. Visible label text is
# what a person reads, and it survives the redesigns that churn the markup.
LABEL_FALLBACKS: list[tuple[str, str]] = [
    ("First Name", "first_name"),
    ("Last Name", "last_name"),
    ("Full name", "full_name"),
    ("Email", "email"),
    ("Phone", "phone"),
    ("LinkedIn", "linkedin"),
    ("Website", "website"),
    ("GitHub", "github"),
]

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


def _fill_by_label(page: Any, label: str, value: str) -> bool:
    """Fill the first visible input whose label contains `label`.

    Only ever writes into an input that is currently empty, so this cannot undo
    a correct value the selector pass already put there.
    """
    if not value:
        return False
    try:
        locator = page.get_by_label(label, exact=False)
        count = locator.count()
    except Exception:
        return False
    # One label can resolve to several elements: Greenhouse keeps a legacy
    # input alongside the one the applicant sees, and the selector pass has
    # usually filled the legacy one already. Scan for the first that is both
    # visible and still empty rather than assuming .first is the real one.
    for index in range(min(count, 5)):
        try:
            candidate = locator.nth(index)
            if not candidate.is_visible():
                continue
            if (candidate.input_value() or "").strip():
                continue
            candidate.fill(value)
            return True
        except Exception:
            continue
    return False


def _wait_for_form(page: Any, ats: str, timeout_seconds: int) -> bool:
    """Wait for the form itself, not just the document.

    `domcontentloaded` fires before a React board has rendered anything, so
    without this the fill pass runs against an empty page, finds none of its
    fields, and the run aborts reporting a form that was simply not there yet.
    """
    budget = max(1, min(timeout_seconds, 20)) * 1000
    for selector, _attribute in FIELD_MAP.get(ats, []):
        try:
            page.wait_for_selector(selector, state="visible", timeout=budget)
            return True
        except Exception:
            continue
    return False


def _screenshot(page: Any, path: Path) -> bool:
    """Best-effort. A screenshot is an artifact, never a reason to abandon a run.

    Chromium can fail `captureScreenshot` on a tall or still-painting page, and
    letting that propagate would throw away a form that was filled correctly.
    """
    try:
        page.screenshot(path=str(path), full_page=True)
        return True
    except Exception:
        try:
            page.screenshot(path=str(path))  # viewport only, often succeeds
            return True
        except Exception:
            return False


def _label_query(question: str) -> str:
    """The searchable part of a form label.

    Labels arrive decorated -- "Country*", "Phone *", "Why us?:" -- but the text
    in the DOM is usually the bare question. `get_by_label(exact=False)` does a
    substring match, so searching for the decorated version finds nothing.
    """
    return re.sub(r"[\s*:?]+$", "", str(question or "").strip()).strip()


def _answer_field(page: Any, question: str, value: str) -> bool:
    """Put a stored answer into the field labelled `question`.

    Handles the three shapes an application question actually takes: a text box,
    a textarea, and a dropdown. Anything else is left alone rather than poked at.
    """
    if not value:
        return False
    try:
        locator = page.get_by_label(_label_query(question), exact=False)
        count = locator.count()
    except Exception:
        return False
    for index in range(min(count, 5)):
        try:
            element = locator.nth(index)
            if not element.is_visible():
                continue
            tag = str(element.evaluate("e => e.tagName") or "").lower()
            if tag == "select":
                try:
                    element.select_option(label=value)
                except Exception:
                    element.select_option(value)
                return True
            if (element.input_value() or "").strip():
                continue
            element.fill(value)
            return True
        except Exception:
            continue
    return False


def _settle_after_upload(page: Any) -> None:
    """Give a resume parser time to finish rewriting the form.

    Greenhouse re-renders the name and email inputs once it has read the file.
    Typing into them while that is in flight loses the value.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    try:
        page.wait_for_timeout(1500)
    except Exception:
        pass


def _has_captcha(page: Any) -> bool:
    for marker in CAPTCHA_MARKERS:
        try:
            if page.locator(marker).count() > 0:
                return True
        except Exception:
            continue
    return False


def _unfilled_required(page: Any) -> list[str]:
    """Required inputs still empty after our pass, excluding ones we won't answer.

    Naming these well is the whole value of the check. Whatever is left here is
    what a human has to go and finish by hand, and "(unnamed)" sends them to a
    screenshot to play spot-the-difference. Modern React form kits -- including
    Greenhouse's current board -- render required inputs with no name, no id, no
    label and no aria-label, so the fallbacks below walk outward through the DOM
    looking for any text a person would recognize.
    """
    try:
        return page.evaluate(
            """() => {
                const skip = /gender|race|ethnic|veteran|disability|orientation|pronoun|self.?identif|voluntary|hispanic/i;
                const clean = s => (s || '').replace(/\\s+/g, ' ').trim();

                const describe = (el, index) => {
                    const byLabel = el.labels && el.labels[0] ? el.labels[0].innerText : '';
                    if (clean(byLabel)) return clean(byLabel);

                    const aria = el.getAttribute('aria-label');
                    if (clean(aria)) return clean(aria);

                    const owner = el.getAttribute('aria-labelledby');
                    if (owner) {
                        const node = document.getElementById(owner);
                        if (node && clean(node.innerText)) return clean(node.innerText);
                    }
                    if (clean(el.placeholder)) return clean(el.placeholder);
                    if (clean(el.name)) return clean(el.name);
                    if (clean(el.id)) return clean(el.id);

                    const wrapper = el.closest('label');
                    if (wrapper && clean(wrapper.innerText)) return clean(wrapper.innerText);

                    // Walk up a few levels looking for the question text a
                    // person would read above the box.
                    let node = el.parentElement;
                    for (let depth = 0; node && depth < 4; depth++, node = node.parentElement) {
                        const label = node.querySelector('label, legend, [class*="label"]');
                        if (label && clean(label.innerText)) return clean(label.innerText);
                        depth++;
                    }
                    return `unlabelled ${el.type || el.tagName.toLowerCase()} field #${index + 1}`;
                };

                const out = [];
                const all = document.querySelectorAll(
                    'input[required], select[required], textarea[required], ' +
                    '[aria-required="true"]'
                );
                [...all].forEach((el, index) => {
                    if (el.type === 'hidden' || el.disabled) return;
                    const label = describe(el, index);
                    if (skip.test(label)) return;
                    const empty = el.type === 'file' ? el.files.length === 0 : !el.value;
                    if (empty) out.push(label.slice(0, 70));
                });
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
    answer_lookup: Callable[[str], str | None] | None = None,
) -> DispatchResult:
    """Fill and (unless dry_run) submit one application form.

    `answer_lookup` maps a form question to a stored answer, or None. It is a
    callable rather than a database handle so this module stays free of the
    schema, and so a test can hand it a dictionary.
    """
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

            # A board URL is not a promise about where you land. Plenty of
            # companies point their Greenhouse board at their own careers site,
            # and this tool is about to type someone's name, email, and phone
            # number into whatever page it is looking at. Re-check the host
            # after navigation and refuse anything we did not recognize.
            landed = detect_ats(page.url)
            if landed != ats:
                _screenshot(page, screenshot)
                browser.close()
                where = "an unrecognized site" if landed == "unknown" else landed
                return DispatchResult(
                    False,
                    "ats_form",
                    f"{apply_url} redirected to {where} ({page.url}). Refusing to enter "
                    "personal details on a page this tool cannot identify -- apply by hand.",
                    artifacts=[str(screenshot)],
                )

            _wait_for_form(page, ats, config.timeout_seconds)

            if _has_captcha(page):
                _screenshot(page, screenshot)
                browser.close()
                return DispatchResult(
                    False,
                    "ats_form",
                    "a CAPTCHA is present -- stopping. Finish this one by hand.",
                    artifacts=[str(screenshot)],
                )

            filled: list[str] = []

            # The resume goes first, deliberately. Greenhouse parses the upload
            # and writes its own guesses at name and email into the form, which
            # discards anything typed beforehand. Uploading first means the
            # parser runs first and the values below overwrite it -- the record
            # in the database wins over a guess made from a PDF.
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
                _settle_after_upload(page)

            for selector, attribute in FIELD_MAP.get(ats, []):
                if _fill_first(page, [selector], getattr(fields, attribute, "")):
                    filled.append(attribute)

            # Then by visible label, for the fields the selectors could not
            # reach. `_fill_by_label` skips anything already holding a value, so
            # this only ever adds.
            for label, attribute in LABEL_FALLBACKS:
                if _fill_by_label(page, label, getattr(fields, attribute, "")):
                    filled.append(f"{attribute} (by label)")

            if fields.cover_letter_text:
                if _fill_first(page, COVER_LETTER_SELECTORS.get(ats, []), fields.cover_letter_text):
                    filled.append("cover_letter")

            _screenshot(page, screenshot)
            artifacts.append(str(screenshot))

            # Nothing matched. The page is not the form we expected, so the
            # "no outstanding required fields" check below would be answering a
            # question about a page with no fields in it -- which reads as
            # success and walks on to click submit.
            if not filled:
                browser.close()
                return DispatchResult(
                    False,
                    "ats_form",
                    f"none of the expected {ats} fields were on the page -- its layout has "
                    "changed, or the posting applies somewhere else. Apply by hand.",
                    artifacts=artifacts,
                )

            outstanding = _unfilled_required(page)

            # Whatever is left is a question the resume cannot answer: work
            # authorization, notice period, why-this-company. If the candidate
            # has written an answer down, use it verbatim. If not, this run
            # stops -- inventing a "no" to a sponsorship question would be a lie
            # told to an employer under their name.
            if outstanding and answer_lookup is not None:
                for question in list(outstanding):
                    stored = answer_lookup(question)
                    if stored and _answer_field(page, question, stored):
                        filled.append(f"answered: {question[:40]}")
                _screenshot(page, screenshot)
                outstanding = _unfilled_required(page)

            if outstanding:
                browser.close()
                return DispatchResult(
                    False,
                    "ats_form",
                    "required question(s) with no stored answer: "
                    + ", ".join(outstanding[:6])
                    + ".  Record answers with `jobsearch answers add` and this will "
                    "go through next run.",
                    artifacts=artifacts,
                    unanswered=list(outstanding),
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
            # The form is already submitted by this point. A failed screenshot
            # must not turn a successful application into a reported failure.
            if _screenshot(page, confirmation):
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
