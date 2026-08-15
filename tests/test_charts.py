"""Tests for the SVG charts.

Mostly about the properties that make a chart honest rather than pretty: marks
sized to spec, values never reachable only by hovering, and text from the job
boards escaped like everywhere else.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobsearch import db  # noqa: E402
from jobsearch.config import Config  # noqa: E402
from jobsearch.web import charts  # noqa: E402
from jobsearch.web.server import App  # noqa: E402


class FormattingTests(unittest.TestCase):
    def test_thousands_are_grouped(self) -> None:
        self.assertEqual(charts._fmt(1284), "1,284")

    def test_large_numbers_compact(self) -> None:
        self.assertEqual(charts._fmt(12900), "12.9K")
        self.assertEqual(charts._fmt(20000), "20K")

    def test_axis_tops_round_up_to_readable_numbers(self) -> None:
        self.assertEqual(charts._nice_max(1284), 2000)
        self.assertEqual(charts._nice_max(7), 10)
        self.assertEqual(charts._nice_max(0), 1)


class MarkSpecTests(unittest.TestCase):
    """The viewBox is in pixels, so the specs have to hold in viewBox units."""

    def test_columns_never_exceed_the_bar_cap(self) -> None:
        svg = charts.column_chart([("0", 5), ("10", 9)])
        widths = [float(w) for w in re.findall(r'<rect [^>]*width="([\d.]+)"', svg)]
        self.assertTrue(widths)
        self.assertLessEqual(max(widths), charts.BAR_MAX)

    def test_bars_are_thin(self) -> None:
        svg = charts.bar_chart([("greenhouse", 1146), ("remotive", 18)])
        heights = [float(h) for h in re.findall(r'<rect [^>]*height="([\d.]+)"', svg)]
        self.assertTrue(heights)
        self.assertLessEqual(max(heights), charts.BAR_MAX)

    def test_the_line_is_two_pixels_and_round(self) -> None:
        svg = charts.line_chart([("01", 3), ("02", 9), ("03", 5)])
        self.assertIn('stroke-width="2"', svg)
        self.assertIn('stroke-linecap="round"', svg)

    def test_the_area_wash_is_not_a_saturated_block(self) -> None:
        svg = charts.line_chart([("01", 3), ("02", 9)])
        self.assertIn('fill-opacity="0.1"', svg)

    def test_the_end_marker_carries_a_surface_ring(self) -> None:
        svg = charts.line_chart([("01", 3), ("02", 9)])
        self.assertIn(f'stroke="{charts.SURFACE}" stroke-width="2"', svg)

    def test_gridlines_are_solid_hairlines(self) -> None:
        svg = charts.column_chart([("0", 5)])
        self.assertIn('stroke-width="1"', svg)
        self.assertNotIn("stroke-dasharray", svg)


class AccessibilityTests(unittest.TestCase):
    def test_every_chart_ships_a_table_twin(self) -> None:
        for svg in (
            charts.column_chart([("0", 5)]),
            charts.bar_chart([("a", 1)]),
            charts.line_chart([("01", 1), ("02", 2)]),
            charts.split_bar("evidenced", 10, "unevidenced", 10),
        ):
            with self.subTest(chart=svg[:40]):
                self.assertIn("chart-table", svg)
                self.assertIn("<table>", svg)

    def test_two_series_get_a_legend(self) -> None:
        svg = charts.split_bar("evidenced", 10, "unevidenced", 4)
        self.assertIn("evidenced", svg)
        self.assertIn("unevidenced", svg)

    def test_charts_are_labelled_for_screen_readers(self) -> None:
        svg = charts.bar_chart([("a", 1)], title="Jobs by board")
        self.assertIn('role="img"', svg)
        self.assertIn('aria-label="Jobs by board"', svg)

    def test_marks_carry_hover_titles(self) -> None:
        svg = charts.bar_chart([("greenhouse", 1146)])
        self.assertIn("<title>greenhouse: 1,146</title>", svg)


class EscapingTests(unittest.TestCase):
    """Category names reach this from job boards, so they are untrusted."""

    def test_a_category_name_cannot_inject_markup(self) -> None:
        svg = charts.bar_chart([("<script>alert(1)</script>", 3)])
        self.assertNotIn("<script>", svg)
        self.assertIn("&lt;script&gt;", svg)

    def test_a_bin_label_cannot_inject_markup(self) -> None:
        svg = charts.column_chart([("<img src=x onerror=1>", 3)])
        self.assertNotIn("<img", svg)


class EmptyStateTests(unittest.TestCase):
    def test_no_data_says_so_instead_of_drawing_an_empty_frame(self) -> None:
        self.assertIn("Nothing to plot", charts.column_chart([]))
        self.assertIn("Nothing to plot", charts.bar_chart([]))
        self.assertIn("Not enough history", charts.line_chart([("01", 1)]))

    def test_all_zero_values_do_not_divide_by_zero(self) -> None:
        svg = charts.bar_chart([("a", 0), ("b", 0)])
        self.assertIn("<svg", svg)

    def test_split_bar_with_nothing_in_it(self) -> None:
        self.assertIn("Nothing to plot", charts.split_bar("a", 0, "b", 0))


class TerminalPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "t.db"
        self.app = App(str(self.db_path), Config(), "tok")

    def test_it_renders_on_an_empty_database(self) -> None:
        status, body = self.app.get("/terminal", {})
        self.assertEqual(status, 200)
        self.assertIn("Terminal", body)

    def test_it_renders_with_data(self) -> None:
        conn = db.connect(self.db_path)
        for index, (source, score) in enumerate(
            [("greenhouse", 41.0), ("remoteok", 12.5), ("greenhouse", 33.0)]
        ):
            db.insert_row(conn, "jobs", {
                "source": source, "company": f"Co{index}", "title": "Engineer",
                "fit_score": score, "discovered_at": "2026-08-14T10:00:00",
                "fingerprint": f"fp{index}", "status": "scored",
            })
        conn.commit()
        conn.close()

        status, body = self.app.get("/terminal", {})
        self.assertEqual(status, 200)
        self.assertIn("greenhouse", body)
        self.assertIn("<svg", body)


if __name__ == "__main__":
    unittest.main()
