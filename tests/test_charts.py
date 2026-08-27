"""Tests for the charts.

The drawing moved to the browser, so what is testable here is the contract
between the two halves: the payload the server hands over, the table that stays
behind when JavaScript does not run, and the escaping -- category labels arrive
from job boards and land inside an HTML attribute.

The mark specs are asserted against the engine source. That is a weaker check
than measuring a rendered bar, and it is deliberate: the real geometry check is
opening the page and looking at it, which is how the last two chart bugs were
found. These catch a spec being edited away by accident.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobsearch import db  # noqa: E402
from jobsearch.config import Config  # noqa: E402
from jobsearch.web import charts  # noqa: E402
from jobsearch.web.assets import SITE_JS, SITE_JS_HASH  # noqa: E402
from jobsearch.web.server import App  # noqa: E402


def payload(html: str) -> dict:
    """Pull the chart payload back out of the data attribute."""
    match = re.search(r'data-chart="([^"]+)"', html)
    assert match, "no chart payload in output"
    raw = (
        match.group(1)
        .replace("&quot;", '"')
        .replace("&#x27;", "'")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
    )
    return json.loads(raw)


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


class PayloadTests(unittest.TestCase):
    def test_each_form_declares_its_kind(self) -> None:
        cases = {
            charts.column_chart([("0", 5)]): "columns",
            charts.bar_chart([("a", 1)]): "bars",
            charts.line_chart([("01", 1), ("02", 2)]): "line",
            charts.split_bar("evidenced", 3, "unevidenced", 1): "split",
        }
        for html, kind in cases.items():
            with self.subTest(kind=kind):
                self.assertEqual(payload(html)["kind"], kind)

    def test_rows_survive_as_label_value_pairs(self) -> None:
        data = payload(charts.bar_chart([("greenhouse", 1146), ("remotive", 18)]))
        self.assertEqual(data["rows"], [["greenhouse", 1146.0], ["remotive", 18.0]])

    def test_the_title_travels_with_the_data(self) -> None:
        data = payload(charts.bar_chart([("a", 1)], title="Jobs by board"))
        self.assertEqual(data["title"], "Jobs by board")


class FallbackTests(unittest.TestCase):
    """With no JavaScript the table is the chart, so it must always be there."""

    def test_every_form_ships_a_table(self) -> None:
        for html in (
            charts.column_chart([("0", 5)]),
            charts.bar_chart([("a", 1)]),
            charts.line_chart([("01", 1), ("02", 2)]),
            charts.split_bar("evidenced", 10, "unevidenced", 10),
        ):
            with self.subTest(chart=html[:40]):
                self.assertIn("chart-table", html)
                self.assertIn("<table>", html)

    def test_the_table_carries_the_real_values(self) -> None:
        html = charts.bar_chart([("greenhouse", 1146)])
        self.assertIn("greenhouse", html)
        self.assertIn("1,146", html)


class EscapingTests(unittest.TestCase):
    """Labels come from job boards and land inside an HTML attribute."""

    def test_a_category_name_cannot_break_out_of_the_attribute(self) -> None:
        html = charts.bar_chart([('" onmouseover="alert(1)', 3)])
        self.assertNotIn('onmouseover="alert(1)"', html)

    def test_a_script_tag_is_escaped_in_both_halves(self) -> None:
        html = charts.column_chart([("<script>alert(1)</script>", 3)])
        self.assertNotIn("<script>alert(1)</script>", html)
        # And it survives the round trip intact as text, not as markup.
        self.assertEqual(payload(html)["rows"][0][0], "<script>alert(1)</script>")


class EmptyStateTests(unittest.TestCase):
    def test_no_data_says_so_instead_of_drawing_an_empty_frame(self) -> None:
        self.assertIn("Nothing to plot", charts.column_chart([]))
        self.assertIn("Nothing to plot", charts.bar_chart([]))
        self.assertIn("Not enough history", charts.line_chart([("01", 1)]))
        self.assertIn("Nothing to plot", charts.split_bar("a", 0, "b", 0))

    def test_all_zero_values_still_produce_a_payload(self) -> None:
        data = payload(charts.bar_chart([("a", 0), ("b", 0)]))
        self.assertEqual(data["rows"], [["a", 0.0], ["b", 0.0]])


class ProgressiveEnhancementTests(unittest.TestCase):
    """Scroll-reveal must never be a requirement for content to be visible.

    Caught by a full-page screenshot before real scroll events had ever fired:
    every `.rise` section past the fold was blank. The CSS was hiding content
    unconditionally, with only the inline script able to reveal it -- so a
    browser where that script never runs (disabled, blocked, thrown, or just
    slow) is left with entire sections invisible forever, not just unanimated.
    The fix inverts which side does the hiding: content is visible by default,
    and the script may only ever add the hidden state right before it starts
    watching for the reveal.
    """

    def test_bare_rise_is_never_hidden_by_css(self) -> None:
        from jobsearch.web.html import STYLESHEET

        self.assertNotIn(".rise {\n  opacity: 0", STYLESHEET)
        self.assertNotIn(".bubble.rise { opacity: 0", STYLESHEET)

    def test_hiding_is_scoped_to_the_pending_state(self) -> None:
        from jobsearch.web.html import STYLESHEET

        self.assertIn(".rise.pending {", STYLESHEET)
        self.assertIn("opacity: 0", STYLESHEET.split(".rise.pending {", 1)[1][:80])

    def test_the_reduced_motion_and_no_observer_path_never_adds_pending(self) -> None:
        # That early return has to leave the DOM untouched -- if it added
        # 'pending' without also guaranteeing 'in' gets added synchronously,
        # this path would reintroduce the exact bug the split was meant to fix.
        branch = SITE_JS.split("function reveal() {", 1)[1].split("if (reduceMotion", 1)[1]
        early_return = branch.split("return;", 1)[0]
        self.assertNotIn("classList.add('pending')", early_return)

    def test_pending_is_added_only_alongside_observing(self) -> None:
        reveal_fn = SITE_JS.split("function reveal() {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("classList.add('pending')", reveal_fn)
        self.assertIn("io.observe(n)", reveal_fn)


class EngineTests(unittest.TestCase):
    """Properties of the client-side engine that must not be edited away."""

    def test_it_honours_reduced_motion(self) -> None:
        self.assertIn("prefers-reduced-motion", SITE_JS)

    def test_marks_stay_thin(self) -> None:
        # Columns cap at 26, bars draw at 16. Both are under the 24-32 band that
        # starts reading as slabs.
        self.assertIn("Math.min(26, slot - 8)", SITE_JS)
        self.assertIn("bh = 16", SITE_JS)

    def test_the_line_is_two_pixels_with_round_joins(self) -> None:
        self.assertIn("'stroke-width': 2", SITE_JS)
        self.assertIn("'stroke-linecap': 'round'", SITE_JS)

    def test_the_area_is_a_wash_not_a_block(self) -> None:
        self.assertIn("'fill-opacity': '.10'", SITE_JS)

    def test_hit_targets_are_larger_than_the_marks(self) -> None:
        # Whole-slot and whole-row hit rectangles, so a 2px bar is still hoverable.
        self.assertIn("'class': 'hit'", SITE_JS)

    def test_only_the_two_validated_hues_appear(self) -> None:
        hexes = set(re.findall(r"#[0-9a-fA-F]{6}", SITE_JS))
        self.assertEqual(hexes, {"#4169e1", "#c8102e"})


class CspTests(unittest.TestCase):
    def test_the_hash_matches_the_script_actually_served(self) -> None:
        import base64
        import hashlib

        from jobsearch.web.html import layout

        digest = hashlib.sha256(SITE_JS.encode("utf-8")).digest()
        self.assertEqual(SITE_JS_HASH, "sha256-" + base64.b64encode(digest).decode())
        # And the page really does embed exactly that string.
        self.assertIn(SITE_JS, layout("t", "<p>x</p>"))


class TerminalPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "t.db"
        self.app = App(str(self.db_path), Config(), "tok")

    def test_it_renders_on_an_empty_database(self) -> None:
        # /terminal serves the one Analytics page now (jobsearch/web/
        # evoque_pages.analytics). What this guards is unchanged: the URL still
        # returns a page, and an empty database says so instead of blowing up.
        status, body = self.app.get("/terminal", {})
        self.assertEqual(status, 200)
        self.assertIn("Analytics", body)
        self.assertIn("Nothing to plot yet", body)

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
        # Charts are inline SVG rendered server-side rather than a `data-chart`
        # placeholder hydrated later, so assert the drawn figure itself.
        self.assertIn("Source reach", body)
        self.assertIn("<svg", body)


if __name__ == "__main__":
    unittest.main()
