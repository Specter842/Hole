"""Tests for ATS form filling, especially the refusals.

No browser. A fake `playwright.sync_api` is installed for the duration of each
test, so these run whether or not chromium is on the machine.

The guards under test all exist because of the same failure: this code types a
real person's name, email, and phone number into a page and can click submit.
Every one of them is a reason to stop.
"""

from __future__ import annotations

import sys
import tempfile
import types as pytypes
import unittest
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobsearch.config import AtsConfig  # noqa: E402
from jobsearch.dispatch import ats_form  # noqa: E402

GREENHOUSE = "https://boards.greenhouse.io/acme/jobs/9"


class FakeElement:
    def __init__(self, *, visible: bool = True, value: str = "", name: str = "") -> None:
        self._visible = visible
        self.value = value
        self.name = name
        self.files: list[str] = []
        self.clicked = False

    def is_visible(self) -> bool:
        return self._visible

    def input_value(self) -> str:
        return self.value

    def fill(self, value: str) -> None:
        if not self._visible:
            raise RuntimeError("not visible")
        self.value = value

    def set_input_files(self, path: str) -> None:
        self.files.append(path)

    def click(self) -> None:
        self.clicked = True


class FakeLocator:
    def __init__(self, elements: list[FakeElement]) -> None:
        self.elements = elements

    def count(self) -> int:
        return len(self.elements)

    @property
    def first(self) -> FakeElement:
        return self.elements[0]

    def nth(self, index: int) -> FakeElement:
        return self.elements[index]


class FakePage:
    def __init__(
        self,
        *,
        lands_on: str | None = None,
        selectors: dict[str, list[FakeElement]] | None = None,
        labels: dict[str, list[FakeElement]] | None = None,
        required: list[str] | None = None,
    ) -> None:
        self.url = ""
        self._lands_on = lands_on
        self.selectors = selectors or {}
        self.labels = labels or {}
        self.required = required or []
        self.order: list[str] = []  # what happened, in sequence

    # -- navigation ------------------------------------------------------
    def goto(self, url: str, **_kwargs: object) -> None:
        self.url = self._lands_on or url

    def set_default_timeout(self, _ms: int) -> None:
        pass

    def wait_for_selector(self, selector: str, **_kwargs: object):
        if self.selectors.get(selector):
            return self.selectors[selector][0]
        raise RuntimeError("no such selector")

    def wait_for_load_state(self, *_a: object, **_k: object) -> None:
        pass

    def wait_for_timeout(self, _ms: int) -> None:
        pass

    # -- querying --------------------------------------------------------
    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self.selectors.get(selector, []))

    def get_by_label(self, label: str, **_kwargs: object) -> FakeLocator:
        return FakeLocator(self.labels.get(label, []))

    def evaluate(self, _script: str) -> list[str]:
        return self.required

    def screenshot(self, path: str, **_kwargs: object) -> None:
        Path(path).write_bytes(b"png")

    def close(self) -> None:
        pass


@contextmanager
def fake_playwright(page: FakePage):
    class FakeBrowser:
        def new_context(self, **_k: object):
            return self

        def new_page(self):
            return page

        def close(self) -> None:
            pass

    class FakeChromium:
        def launch(self, **_k: object):
            return FakeBrowser()

    class FakeDriver:
        chromium = FakeChromium()

        def __enter__(self):
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

    module = pytypes.ModuleType("playwright.sync_api")
    module.sync_playwright = lambda: FakeDriver()
    parent = pytypes.ModuleType("playwright")
    parent.sync_api = module

    saved = {n: sys.modules.get(n) for n in ("playwright", "playwright.sync_api")}
    sys.modules["playwright"] = parent
    sys.modules["playwright.sync_api"] = module
    try:
        yield
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


def make_fields(tmp: Path) -> ats_form.ApplicantFields:
    resume = tmp / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4 fake")
    return ats_form.ApplicantFields(
        first_name="Sam", last_name="Rivera", full_name="Sam Rivera",
        email="sam@example.com", phone="555-0100", resume_path=resume,
    )


class AtsSubmitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.config = AtsConfig(enabled=True, headless=True, timeout_seconds=5,
                                screenshot_dir="shots")
        self.fields = make_fields(self.tmp)

    def _submit(self, page: FakePage, **kwargs: object):
        with fake_playwright(page):
            return ats_form.submit(
                self.config, apply_url=GREENHOUSE, fields=self.fields,
                project_root=self.tmp, slug="t", dry_run=True, **kwargs,
            )

    # -- the redirect guard ---------------------------------------------

    def test_redirect_to_an_unknown_host_is_refused(self) -> None:
        page = FakePage(lands_on="https://stripe.com/careers/listing/123")
        result = self._submit(page)
        self.assertFalse(result.ok)
        self.assertIn("redirected", result.detail)
        self.assertIn("Refusing to enter personal details", result.detail)

    def test_redirect_within_the_same_ats_is_allowed(self) -> None:
        # job-boards.greenhouse.io is where Greenhouse actually serves the form.
        page = FakePage(
            lands_on="https://job-boards.greenhouse.io/acme/jobs/9",
            selectors={"#first_name": [FakeElement()], "#email": [FakeElement()]},
        )
        result = self._submit(page)
        self.assertTrue(result.ok, result.detail)

    def test_nothing_is_typed_when_the_host_is_wrong(self) -> None:
        element = FakeElement()
        page = FakePage(
            lands_on="https://elsewhere.example.com/apply",
            selectors={"#first_name": [element]},
        )
        self._submit(page)
        self.assertEqual(element.value, "")  # never touched

    # -- the empty-fill guard -------------------------------------------

    def test_a_page_with_none_of_our_fields_is_refused(self) -> None:
        page = FakePage(selectors={})  # nothing matches
        result = self._submit(page)
        self.assertFalse(result.ok)
        self.assertIn("layout has changed", result.detail)

    # -- ordering --------------------------------------------------------

    def test_the_resume_is_uploaded_before_the_text_fields_are_filled(self) -> None:
        """Greenhouse parses the upload and overwrites name and email, so our
        values have to be written after it, not before."""
        upload = FakeElement()
        first = FakeElement()
        page = FakePage(
            selectors={"#resume": [upload], "#first_name": [first], "#email": [FakeElement()]},
        )
        result = self._submit(page)
        self.assertTrue(result.ok, result.detail)
        self.assertEqual(upload.files, [str(self.fields.resume_path)])
        self.assertEqual(first.value, "Sam")  # survived the upload

    # -- unanswerable questions -----------------------------------------

    def test_required_questions_we_will_not_answer_stop_the_run(self) -> None:
        page = FakePage(
            selectors={"#first_name": [FakeElement()]},
            required=["Why Anthropic?*", "Do you require visa sponsorship?*"],
        )
        result = self._submit(page)
        self.assertFalse(result.ok)
        self.assertIn("Why Anthropic?*", result.detail)

    def test_dry_run_never_clicks_submit(self) -> None:
        button = FakeElement()
        page = FakePage(
            selectors={"#first_name": [FakeElement()], "#submit_app": [button]},
        )
        result = self._submit(page)
        self.assertTrue(result.ok)
        self.assertFalse(button.clicked)

    def test_disabled_channel_does_not_open_a_browser(self) -> None:
        self.config.enabled = False
        result = ats_form.submit(
            self.config, apply_url=GREENHOUSE, fields=self.fields,
            project_root=self.tmp, slug="t",
        )
        self.assertFalse(result.ok)
        self.assertIn("enabled is false", result.detail)


class FillByLabelTests(unittest.TestCase):
    """One label can match several inputs; only one of them is the real box."""

    def test_skips_an_input_that_already_has_a_value(self) -> None:
        filled = FakeElement(value="already there")
        empty = FakeElement()
        page = FakePage(labels={"First Name": [filled, empty]})
        self.assertTrue(ats_form._fill_by_label(page, "First Name", "Sam"))
        self.assertEqual(filled.value, "already there")
        self.assertEqual(empty.value, "Sam")

    def test_skips_a_hidden_input(self) -> None:
        hidden = FakeElement(visible=False)
        shown = FakeElement()
        page = FakePage(labels={"Email": [hidden, shown]})
        self.assertTrue(ats_form._fill_by_label(page, "Email", "sam@example.com"))
        self.assertEqual(shown.value, "sam@example.com")

    def test_returns_false_when_nothing_matches(self) -> None:
        self.assertFalse(ats_form._fill_by_label(FakePage(), "Nope", "x"))

    def test_an_empty_value_is_never_written(self) -> None:
        element = FakeElement()
        page = FakePage(labels={"Phone": [element]})
        self.assertFalse(ats_form._fill_by_label(page, "Phone", ""))
        self.assertEqual(element.value, "")


class WaitForFormTests(unittest.TestCase):
    def test_returns_true_once_a_known_field_exists(self) -> None:
        page = FakePage(selectors={"#first_name": [FakeElement()]})
        self.assertTrue(ats_form._wait_for_form(page, "greenhouse", 5))

    def test_returns_false_when_the_form_never_appears(self) -> None:
        self.assertFalse(ats_form._wait_for_form(FakePage(), "greenhouse", 1))


if __name__ == "__main__":
    unittest.main()
