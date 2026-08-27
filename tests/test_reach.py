"""Tests for the Reach/Activity charts: bubble cluster, ranked list, donut, heatmap.

Mostly about the same two things every chart test here cares about: the payload
survives escaping intact, and a value is never reachable only by hovering.
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
from jobsearch.web import charts, geo, pages  # noqa: E402
from jobsearch.web.assets import SITE_JS  # noqa: E402
from jobsearch.web.server import App  # noqa: E402


def payload(html: str) -> dict:
    import json

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


class DonutTests(unittest.TestCase):
    def test_the_payload_carries_both_slices(self) -> None:
        data = payload(charts.donut_chart("remote", 286, "onsite", 998, title="Remote vs onsite"))
        self.assertEqual(data["kind"], "donut")
        self.assertEqual(data["rows"], [["remote", 286.0], ["onsite", 998.0]])

    def test_zero_on_both_sides_is_an_empty_state(self) -> None:
        self.assertIn("Nothing to plot", charts.donut_chart("a", 0, "b", 0))

    def test_a_table_twin_exists(self) -> None:
        html = charts.donut_chart("remote", 5, "onsite", 15)
        self.assertIn("chart-table", html)
        self.assertIn("<table>", html)


class HeatmapTests(unittest.TestCase):
    def test_a_populated_cell_survives_in_the_payload(self) -> None:
        cells = {("greenhouse", "0"): 801.0, ("greenhouse", "10"): 273.0}
        html = charts.heatmap_chart(["greenhouse", "remoteok"], ["0", "10"], cells)
        data = payload(html)
        self.assertEqual(data["kind"], "heatmap")
        self.assertEqual(data["grid"][0], [801.0, 273.0])
        # A source with nothing counted is zero, not fabricated or omitted.
        self.assertEqual(data["grid"][1], [0.0, 0.0])

    def test_no_axis_labels_is_an_empty_state(self) -> None:
        self.assertIn("Nothing to plot", charts.heatmap_chart([], [], {}))

    def test_an_all_zero_grid_is_also_an_empty_state(self) -> None:
        html = charts.heatmap_chart(["a"], ["0"], {})
        self.assertIn("Nothing to plot", html)

    def test_the_table_twin_only_lists_populated_cells(self) -> None:
        cells = {("greenhouse", "0"): 801.0}
        html = charts.heatmap_chart(["greenhouse", "remoteok"], ["0", "10"], cells)
        self.assertIn("801", html)
        # remoteok has nothing counted anywhere -- it should not clutter the
        # table with a row of zeros.
        self.assertNotIn("<td>remoteok</td>", html)


class BubbleClusterTests(unittest.TestCase):
    def test_size_scales_with_the_square_root_not_linearly(self) -> None:
        # A 4x board must not render 4x the diameter -- that would be encoding
        # value as radius, so the *area* would mislead by 4x again. A legibility
        # floor on the smallest bubble means the ratio isn't exactly 2:1 either,
        # so this checks the shape of the relationship, not one exact number.
        html = charts.bubble_cluster([("big", 400), ("small", 100)])
        sizes = [float(d) for d in re.findall(r"--d:([\d.]+)px", html)]
        self.assertEqual(len(sizes), 2)
        ratio = sizes[0] / sizes[1]
        self.assertGreater(ratio, 1.0)   # bigger value, bigger bubble
        self.assertLess(ratio, 4.0)      # but compressed well short of linear

    def test_largest_renders_first(self) -> None:
        html = charts.bubble_cluster([("small", 5), ("big", 500)])
        self.assertLess(html.index("big"), html.index("small"))

    def test_a_label_cannot_break_out_of_the_title_attribute(self) -> None:
        html = charts.bubble_cluster([('" onmouseover="alert(1)', 10)])
        self.assertNotIn('onmouseover="alert(1)"', html)

    def test_empty_input_is_an_empty_state(self) -> None:
        self.assertIn("Nothing to plot", charts.bubble_cluster([]))


class RankedListTests(unittest.TestCase):
    def test_rows_are_numbered_in_order(self) -> None:
        html = charts.ranked_list([("Austin", 40), ("Berlin", 25), ("Remote", 10)])
        self.assertLess(html.index("Austin"), html.index("Berlin"))
        self.assertLess(html.index("Berlin"), html.index("Remote"))
        self.assertIn(">01<", html)
        self.assertIn(">03<", html)

    def test_share_is_of_the_total_not_of_the_max(self) -> None:
        html = charts.ranked_list([("a", 50), ("b", 50)])
        # Two equal rows against a shared total of 100 -- each bar is 50%.
        self.assertIn("--w:50.0%", html)

    def test_a_location_string_is_escaped(self) -> None:
        html = charts.ranked_list([("<script>alert(1)</script>", 5)])
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_empty_input_is_an_empty_state(self) -> None:
        self.assertIn("Nothing to plot", charts.ranked_list([]))


class QueryTests(unittest.TestCase):
    """The page-level queries that feed these charts."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "t.db"
        self.conn = db.connect(self.db_path)
        self.addCleanup(self.conn.close)

    _job_seq = 0

    def _job(self, **overrides: object) -> None:
        # A counter, not id(row): CPython can and does reuse a freed dict's
        # address on the next allocation, so two rows built back-to-back could
        # collide on a fingerprint keyed off id().
        QueryTests._job_seq += 1
        row = {
            "source": "greenhouse", "company": "Acme", "title": "Engineer",
            "location": "Remote", "remote": 1, "fit_score": None,
            "discovered_at": "2026-08-14T10:00:00", "status": "new",
        }
        row.update(overrides)
        row["fingerprint"] = f"fp-{QueryTests._job_seq}"
        db.insert_row(self.conn, "jobs", row)

    def test_remote_split_counts_both_sides(self) -> None:
        self._job(remote=1)
        self._job(remote=1)
        self._job(remote=0)
        self.conn.commit()
        remote, onsite = pages._remote_split(self.conn)
        self.assertEqual((remote, onsite), (2.0, 1.0))

    def test_by_location_keeps_compound_strings_intact(self) -> None:
        # A multi-city Greenhouse posting reports all cities in one string;
        # collapsing it would claim precision the posting does not have.
        self._job(location="San Francisco, CA | New York, NY")
        self.conn.commit()
        rows = pages._by_location(self.conn)
        self.assertEqual(rows[0][0], "San Francisco, CA | New York, NY")

    def test_fit_by_source_only_counts_scored_jobs(self) -> None:
        self._job(source="greenhouse", fit_score=5.0)
        self._job(source="greenhouse", fit_score=45.0)
        self._job(source="remoteok", fit_score=None)  # unscored -- absent, not zero
        self.conn.commit()
        sources, bands, cells = pages._fit_by_source(self.conn)
        self.assertIn("greenhouse", sources)
        self.assertEqual(cells.get(("greenhouse", "0")), 1.0)
        self.assertEqual(cells.get(("greenhouse", "40")), 1.0)
        self.assertNotIn(("remoteok", "0"), cells)

    def test_bands_run_in_fixed_order_not_by_size(self) -> None:
        _sources, bands, _cells = pages._fit_by_source(self.conn)
        self.assertEqual(bands, [str(n) for n in range(0, 100, 10)])

    def test_postings_by_country_only_counts_named_countries(self) -> None:
        self._job(location="Berlin, Germany")
        self._job(location="Remote (US/UK)")
        self._job(location="Remote")  # no country named -- must not appear at all
        self._job(location="Cambridge")  # ambiguous city -- must not be guessed
        self.conn.commit()
        rows = dict(pages._postings_by_country(self.conn))
        self.assertEqual(rows.get("Germany"), 1.0)
        self.assertEqual(rows.get("United States"), 1.0)
        self.assertEqual(rows.get("United Kingdom"), 1.0)
        self.assertEqual(sum(rows.values()), 3.0)  # not 4 -- the two skipped rows add nothing

    def test_applications_by_country_follows_the_jobs_join(self) -> None:
        self._job(location="Paris, France")
        self.conn.commit()
        job_id = self.conn.execute("SELECT id FROM jobs").fetchone()["id"]
        db.insert_application(self.conn, {"job_id": job_id, "status": "sent"})
        self.conn.commit()
        rows = dict(pages._applications_by_country(self.conn))
        self.assertEqual(rows.get("France"), 1.0)


class GeoTests(unittest.TestCase):
    def test_a_named_country_matches_case_insensitively(self) -> None:
        self.assertEqual(geo.extract_countries("remote - germany"), ["Germany"])

    def test_a_compound_string_returns_every_country_named(self) -> None:
        self.assertEqual(
            geo.extract_countries("Remote (US/UK)"), ["United States", "United Kingdom"]
        )

    def test_remote_alone_matches_nothing(self) -> None:
        self.assertEqual(geo.extract_countries("Remote"), [])

    def test_an_unrecognized_city_is_not_guessed_into_a_country(self) -> None:
        self.assertEqual(geo.extract_countries("Cambridge"), [])

    def test_an_abbreviation_does_not_fire_inside_an_unrelated_word(self) -> None:
        # "US" must not match inside "USABLE" or similar -- whole-word only.
        self.assertEqual(geo.extract_countries("Usable Systems Inc, Austin"), [])

    def test_none_and_empty_are_handled(self) -> None:
        self.assertEqual(geo.extract_countries(None), [])
        self.assertEqual(geo.extract_countries(""), [])


class ReachPageIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "t.db"
        self.app = App(str(self.db_path), Config(), "tok")

    def test_reach_renders_real_numbers(self) -> None:
        conn = db.connect(self.db_path)
        db.insert_row(conn, "jobs", {
            "source": "greenhouse", "company": "Acme", "title": "Engineer",
            "location": "Berlin, Germany", "remote": 1, "fingerprint": "fp-1",
            "discovered_at": "2026-08-14T10:00:00",
        })
        conn.commit()
        conn.close()

        status, body = self.app.get("/reach", {})
        self.assertEqual(status, 200)
        self.assertIn("Germany", body)

    def test_it_survives_a_completely_empty_database(self) -> None:
        # /reach serves the server-rendered Analytics page. The thing this
        # test actually guards is that an empty database doesn't blow up the
        # page -- and now that it is server-rendered, the empty state is real
        # text rather than something a client would have to fill in.
        status, body = self.app.get("/reach", {})
        self.assertEqual(status, 200)
        self.assertIn("Analytics", body)
        self.assertIn("Nothing to plot yet", body)

    def test_by_country_section_lists_every_country_a_compound_posting_names(self) -> None:
        conn = db.connect(self.db_path)
        db.insert_row(conn, "jobs", {
            "source": "greenhouse", "company": "Acme", "title": "Engineer",
            "location": "Remote (US/UK)", "remote": 1, "fingerprint": "fp-1",
            "discovered_at": "2026-08-14T10:00:00",
        })
        conn.commit()
        conn.close()

        _status, body = self.app.get("/reach", {})
        self.assertIn("United States", body)
        self.assertIn("United Kingdom", body)


class EngineTests(unittest.TestCase):
    def test_donut_and_heatmap_are_registered(self) -> None:
        self.assertIn("donut: donut", SITE_JS)
        self.assertIn("heatmap: heatmap", SITE_JS)

    def test_heatmap_uses_a_sequential_ramp_not_a_second_hue(self) -> None:
        # Five opacity steps of the one blue, never a second colour -- a
        # heatmap is magnitude, not identity.
        self.assertIn("var STEPS = [0, .16, .38, .64, 1]", SITE_JS)


class TerminalPageIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "t.db"
        self.app = App(str(self.db_path), Config(), "tok")

    def test_terminal_renders_the_new_sections(self) -> None:
        status, body = self.app.get("/terminal", {})
        self.assertEqual(status, 200)
        for heading in ("Reach", "Activity", "Source reach", "Top locations",
                         "Remote vs onsite", "Fit score by source"):
            with self.subTest(heading=heading):
                self.assertIn(heading, body)

    def test_it_survives_a_completely_empty_database(self) -> None:
        status, body = self.app.get("/terminal", {})
        self.assertEqual(status, 200)
        self.assertIn("Nothing to plot yet", body)


class FunnelPageIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "t.db"
        self.app = App(str(self.db_path), Config(), "tok")

    def test_funnel_renders_the_fallback_with_real_stage_counts(self) -> None:
        conn = db.connect(self.db_path)
        db.insert_row(conn, "jobs", {
            "source": "greenhouse", "company": "Acme", "title": "Engineer",
            "location": "Remote", "fingerprint": "fp-1",
            "discovered_at": "2026-08-14T10:00:00",
        })
        conn.commit()
        conn.close()

        status, body = self.app.get("/funnel", {})
        self.assertEqual(status, 200)
        self.assertIn("sourced", body)

    def test_it_survives_a_completely_empty_database(self) -> None:
        status, body = self.app.get("/funnel", {})
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
