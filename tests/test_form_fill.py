"""Tests for the widget-filling logic that lets a form actually complete.

The two functions here decide what gets typed into a real employer's form, so
the tests are mostly about the cases where they must refuse: an answer that
matches two options, and two different questions that happen to share a label.
Both were live bugs found against Figma's board.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobsearch.dispatch import ats_form  # noqa: E402


class MatchOptionTests(unittest.TestCase):
    def test_exact_match_wins(self) -> None:
        self.assertEqual(ats_form._match_option("Yes", ["Yes", "No"]), "Yes")

    def test_case_and_spacing_are_ignored(self) -> None:
        self.assertEqual(ats_form._match_option("yes", ["  Yes  ", "No"]), "  Yes  ")

    def test_unique_prefix_match(self) -> None:
        options = [
            "Austin, Texas, United States",
            "Austintown, Ohio, United States",
            "Boston, Massachusetts, United States",
        ]
        self.assertEqual(ats_form._match_option("Austin, Texas", options), options[0])

    def test_ambiguous_prefix_is_refused(self) -> None:
        # "Austin" prefixes two of these. Picking either would put a city the
        # candidate never named onto a real application.
        options = ["Austin, Texas, United States", "Austin, Indiana, United States"]
        self.assertIsNone(ats_form._match_option("Austin", options))

    def test_exact_beats_a_longer_option_containing_it(self) -> None:
        # "Yes" against ["Yes", "Yes, with conditions"] must resolve to plain
        # "Yes" rather than refusing or upgrading the claim.
        self.assertEqual(
            ats_form._match_option("Yes", ["Yes", "Yes, with conditions"]), "Yes"
        )

    def test_no_match_returns_none(self) -> None:
        self.assertIsNone(ats_form._match_option("Maybe", ["Yes", "No"]))

    def test_empty_inputs_return_none(self) -> None:
        self.assertIsNone(ats_form._match_option("", ["Yes"]))
        self.assertIsNone(ats_form._match_option("Yes", []))


class DedupeFieldsTests(unittest.TestCase):
    """One question per entry, keyed on DOM wrapper rather than label text."""

    def test_a_combobox_and_its_hidden_mirror_collapse(self) -> None:
        fields = [
            {"ref": "a", "group": "g1", "label": "Country*", "kind": "combobox"},
            {"ref": "b", "group": "g1", "label": "Country*", "kind": "text"},
        ]
        out = ats_form._dedupe_fields(fields)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "combobox")  # keep the real widget

    def test_same_label_in_different_wrappers_stays_separate(self) -> None:
        # The live bug: Figma's phone dial-code selector and its country field
        # both describe as "Country". Collapsing them by name threw one away.
        fields = [
            {"ref": "a", "group": "phone", "label": "Country*", "kind": "combobox"},
            {"ref": "b", "group": "addr", "label": "Country*", "kind": "combobox"},
        ]
        self.assertEqual(len(ats_form._dedupe_fields(fields)), 2)

    def test_fields_with_no_wrapper_never_merge(self) -> None:
        fields = [
            {"ref": "a", "group": "", "label": "Question", "kind": "text"},
            {"ref": "b", "group": "", "label": "Question", "kind": "text"},
        ]
        self.assertEqual(len(ats_form._dedupe_fields(fields)), 2)

    def test_unlabelled_fields_are_dropped(self) -> None:
        self.assertEqual(
            ats_form._dedupe_fields([{"ref": "a", "group": "g1", "label": "", "kind": "text"}]),
            [],
        )

    def test_original_order_is_kept(self) -> None:
        fields = [
            {"ref": "a", "group": "g1", "label": "First", "kind": "text"},
            {"ref": "b", "group": "g2", "label": "Second", "kind": "text"},
            {"ref": "c", "group": "g1", "label": "First", "kind": "combobox"},
        ]
        self.assertEqual([f["label"] for f in ats_form._dedupe_fields(fields)], ["First", "Second"])


class LabelQueryTests(unittest.TestCase):
    def test_required_markers_are_stripped(self) -> None:
        self.assertEqual(ats_form._label_query("Country*"), "Country")
        self.assertEqual(ats_form._label_query("Phone *"), "Phone")
        self.assertEqual(ats_form._label_query("Why us?"), "Why us")


class FillElementTests(unittest.TestCase):
    """Filling addresses the stamped ref, and refuses what it cannot resolve."""

    class _Element:
        def __init__(self, tag: str = "INPUT") -> None:
            self.value = ""
            self.checked = False
            self.tag = tag

        def fill(self, value: str) -> None:
            self.value = value

        def select_option(self, value: str = "", label: str = "") -> None:
            self.value = label or value

        def check(self) -> None:
            self.checked = True

    class _Page:
        def __init__(self, elements: dict[str, object]) -> None:
            self.elements = elements

        def locator(self, selector: str):
            ref = selector.split('"')[1] if '"' in selector else selector
            found = self.elements.get(ref)
            outer = self

            class _Loc:
                def count(self) -> int:
                    return 1 if found is not None else 0

                @property
                def first(self):
                    return found

            return _Loc()

    def test_text_field_is_filled(self) -> None:
        element = self._Element()
        page = self._Page({"r1": element})
        ok = ats_form._fill_element(page, {"ref": "r1", "kind": "text"}, "hello")
        self.assertTrue(ok)
        self.assertEqual(element.value, "hello")

    def test_select_uses_the_matched_option_label(self) -> None:
        element = self._Element()
        page = self._Page({"r1": element})
        ok = ats_form._fill_element(
            page, {"ref": "r1", "kind": "select", "options": ["Yes", "No"]}, "yes"
        )
        self.assertTrue(ok)
        self.assertEqual(element.value, "Yes")

    def test_select_refuses_an_answer_matching_no_option(self) -> None:
        element = self._Element()
        page = self._Page({"r1": element})
        ok = ats_form._fill_element(
            page, {"ref": "r1", "kind": "select", "options": ["Yes", "No"]}, "Maybe"
        )
        self.assertFalse(ok)
        self.assertEqual(element.value, "")

    def test_checkbox_is_only_ever_ticked_never_cleared(self) -> None:
        element = self._Element()
        page = self._Page({"r1": element})
        self.assertTrue(ats_form._fill_element(page, {"ref": "r1", "kind": "checkbox"}, "Yes"))
        self.assertTrue(element.checked)
        # A "No" answer leaves the box alone rather than unticking it.
        other = self._Element()
        self.assertFalse(
            ats_form._fill_element(self._Page({"r2": other}), {"ref": "r2", "kind": "checkbox"}, "No")
        )
        self.assertFalse(other.checked)

    def test_a_missing_ref_fills_nothing(self) -> None:
        page = self._Page({})
        self.assertFalse(ats_form._fill_element(page, {"ref": "gone", "kind": "text"}, "x"))

    def test_an_empty_value_is_never_written(self) -> None:
        element = self._Element()
        page = self._Page({"r1": element})
        self.assertFalse(ats_form._fill_element(page, {"ref": "r1", "kind": "text"}, ""))
        self.assertEqual(element.value, "")


if __name__ == "__main__":
    unittest.main()
