"""Tests for the standing-answer bank.

The bank exists so auto-submit stays inside the grounding rule: a form question
is filled from something the candidate wrote, never from something generated.
These tests are mostly about the refusals -- when an answer must *not* be used.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobsearch import answers, db  # noqa: E402

# Verbatim from live Greenhouse boards.
REAL_QUESTIONS = [
    "Do you require visa sponsorship? *",
    "Why Anthropic?*",
    "Country*",
    "Location (City)*",
    "Are you authorized to work in the country for which you applied? *",
]


class AnswerBankTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.conn = db.connect(Path(self._tmp.name) / "t.db")
        self.addCleanup(self.conn.close)


class NormalizeTests(unittest.TestCase):
    def test_decoration_is_stripped(self) -> None:
        self.assertEqual(answers.normalize("Why Anthropic?*"), "why anthropic")
        self.assertEqual(answers.normalize("Country*"), "country")
        self.assertEqual(answers.normalize("  Phone  *  "), "phone")

    def test_case_and_spacing_collapse(self) -> None:
        self.assertEqual(
            answers.normalize("Do   You  Require   VISA Sponsorship?"),
            "do you require visa sponsorship",
        )


class StorageTests(AnswerBankTestCase):
    def test_add_and_list(self) -> None:
        answers.add(self.conn, "visa sponsorship", "No")
        stored = answers.list_all(self.conn)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].answer, "No")
        self.assertEqual(stored[0].pattern, "visa sponsorship")

    def test_adding_the_same_pattern_updates_rather_than_duplicates(self) -> None:
        first = answers.add(self.conn, "visa sponsorship", "No")
        second = answers.add(self.conn, "Visa Sponsorship", "Yes")
        self.assertEqual(first, second)
        self.assertEqual(answers.list_all(self.conn)[0].answer, "Yes")

    def test_an_empty_answer_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            answers.add(self.conn, "notice period", "   ")

    def test_an_empty_pattern_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            answers.add(self.conn, "  ", "something")

    def test_remove(self) -> None:
        answer_id = answers.add(self.conn, "notice period", "Two weeks")
        self.assertTrue(answers.remove(self.conn, answer_id))
        self.assertEqual(answers.list_all(self.conn), [])


class ProtectedQuestionTests(AnswerBankTestCase):
    """Demographic and self-identification questions are never machine-filled."""

    def test_storing_one_is_refused(self) -> None:
        for question in (
            "What is your gender?",
            "Race / Ethnicity",
            "Are you a protected veteran?",
            "Voluntary Self-Identification of Disability",
        ):
            with self.subTest(question=question):
                with self.assertRaises(ValueError):
                    answers.add(self.conn, question, "Prefer not to say")

    def test_lookup_never_answers_one_even_if_a_pattern_would_match(self) -> None:
        # A broad pattern must not become a back door into a protected question.
        answers.add(self.conn, "are you", "Yes")
        self.assertIsNone(answers.find(self.conn, "Are you a protected veteran? *"))

    def test_a_gap_is_not_recorded_for_a_protected_question(self) -> None:
        answers.record_gap(self.conn, "What is your gender?")
        self.assertEqual(answers.gaps(self.conn), [])


class MatchingTests(AnswerBankTestCase):
    def test_matches_a_real_decorated_question(self) -> None:
        answers.add(self.conn, "visa sponsorship", "No")
        found = answers.find(self.conn, "Do you require visa sponsorship? *")
        self.assertIsNotNone(found)
        self.assertEqual(found.answer, "No")

    def test_the_more_specific_pattern_wins(self) -> None:
        answers.add(self.conn, "work", "generic")
        answers.add(self.conn, "authorized to work", "Yes")
        found = answers.find(
            self.conn, "Are you authorized to work in the country for which you applied? *"
        )
        self.assertEqual(found.answer, "Yes")

    def test_a_company_scoped_answer_beats_a_general_one(self) -> None:
        answers.add(self.conn, "why", "Generic reason")
        answers.add(self.conn, "why", "Specific reason", company="Anthropic")
        general = answers.find(self.conn, "Why us?*")
        scoped = answers.find(self.conn, "Why us?*", company="Anthropic")
        self.assertEqual(general.answer, "Generic reason")
        self.assertEqual(scoped.answer, "Specific reason")

    def test_another_companys_answer_is_not_used(self) -> None:
        answers.add(self.conn, "why", "For Anthropic only", company="Anthropic")
        self.assertIsNone(answers.find(self.conn, "Why Figma?*", company="Figma"))

    def test_no_match_returns_none(self) -> None:
        answers.add(self.conn, "visa sponsorship", "No")
        self.assertIsNone(answers.find(self.conn, "What is your notice period?*"))

    def test_resolve_splits_answerable_from_blocking(self) -> None:
        answers.add(self.conn, "visa sponsorship", "No")
        answers.add(self.conn, "authorized to work", "Yes")
        matched, unmatched = answers.resolve(self.conn, REAL_QUESTIONS)
        self.assertEqual(set(matched), {REAL_QUESTIONS[0], REAL_QUESTIONS[4]})
        self.assertIn("Country*", unmatched)


class GapTests(AnswerBankTestCase):
    def test_repeats_are_counted_not_duplicated(self) -> None:
        for _ in range(3):
            answers.record_gap(self.conn, "Country*", company="Figma")
        rows = answers.gaps(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["seen_count"], 3)

    def test_gaps_are_ordered_by_how_often_they_block(self) -> None:
        answers.record_gap(self.conn, "Rare question")
        for _ in range(4):
            answers.record_gap(self.conn, "Common question")
        self.assertEqual(answers.gaps(self.conn)[0]["question"], "Common question")

    def test_answering_a_question_clears_its_gap(self) -> None:
        answers.record_gap(self.conn, "Do you require visa sponsorship? *")
        answers.add(self.conn, "visa sponsorship", "No")
        self.assertEqual(answers.prune_answered(self.conn), 1)
        self.assertEqual(answers.gaps(self.conn), [])

    def test_an_unrelated_answer_does_not_clear_a_gap(self) -> None:
        answers.record_gap(self.conn, "What is your notice period?*")
        answers.add(self.conn, "visa sponsorship", "No")
        self.assertEqual(answers.prune_answered(self.conn), 0)
        self.assertEqual(len(answers.gaps(self.conn)), 1)


if __name__ == "__main__":
    unittest.main()
