"""Tests for entering a career history through the web UI.

The point of this page is that a resume can be built without ever touching the
CLI, so the test that matters most is the last one: enter everything through
HTTP routes, then check the tailoring plan reads it back.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobsearch import db, graph, retrieval  # noqa: E402
from jobsearch.config import Config  # noqa: E402
from jobsearch.web.server import App  # noqa: E402

TOKEN = "test-token"


class BuilderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "t.db"
        self.app = App(str(self.db_path), Config(), TOKEN)

    def post(self, path: str, **fields: str) -> tuple[int, str]:
        return self.app.post(path, {"token": TOKEN, **fields})

    def page(self, path: str = "/profile/build") -> str:
        status, body = self.app.get(path, {})
        self.assertEqual(status, 200)
        return body

    def add_position(self, **overrides: str) -> int:
        payload = {"title": "Senior Engineer", "org": "Acme", "start": "2021-03"}
        payload.update(overrides)
        self.assertEqual(self.post("/profile/experience/add", **payload)[0], 303)
        conn = sqlite3.connect(self.db_path)
        row_id = conn.execute("SELECT MAX(id) FROM experiences").fetchone()[0]
        conn.close()
        return int(row_id)


class RenderingTests(BuilderTestCase):
    def test_an_empty_profile_says_what_to_do(self) -> None:
        body = self.page()
        self.assertIn("No positions yet", body)

    def test_a_position_and_its_accomplishment_render_together(self) -> None:
        exp_id = self.add_position()
        self.post(
            "/profile/achievement/add",
            experience_id=str(exp_id),
            title="Rebuilt the checkout API",
            impact="cut p95 latency 40%",
        )
        body = self.page()
        self.assertIn("Senior Engineer", body)
        self.assertIn("Acme", body)
        self.assertIn("Rebuilt the checkout API", body)
        self.assertIn("cut p95 latency 40%", body)

    def test_values_are_escaped(self) -> None:
        self.add_position(title="<script>alert(1)</script>")
        body = self.page()
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;", body)


class GraphRuleTests(BuilderTestCase):
    """The schema's rules are enforced here too, not just in the CLI."""

    def test_an_accomplishment_with_no_parent_is_refused(self) -> None:
        status, body = self.post("/profile/achievement/add", title="Floating")
        self.assertEqual(status, 400)
        self.assertIn("belong to", body)

    def test_an_accomplishment_needs_a_title(self) -> None:
        exp_id = self.add_position()
        self.assertEqual(
            self.post("/profile/achievement/add", experience_id=str(exp_id), title="")[0],
            400,
        )

    def test_a_position_needs_a_title(self) -> None:
        self.assertEqual(self.post("/profile/experience/add", org="Acme")[0], 400)

    def test_skills_listed_on_a_position_become_evidenced(self) -> None:
        # A skill with no evidence never reaches a resume, so entering one via a
        # position has to create the evidence row, not just the skill.
        self.add_position(skills="Python, PostgreSQL")
        conn = db.connect(self.db_path)
        evidenced = {s["name"] for s in graph.ProfileGraph.load(conn).evidenced_skills}
        conn.close()
        self.assertEqual(evidenced, {"Python", "PostgreSQL"})

    def test_a_bare_skill_stays_unevidenced(self) -> None:
        self.post("/profile/skill/add", name="Rust", proficiency="working")
        conn = db.connect(self.db_path)
        unevidenced = {s["name"] for s in db.unevidenced_skills(conn)}
        conn.close()
        self.assertIn("Rust", unevidenced)


class SecurityTests(BuilderTestCase):
    def test_an_unknown_entity_cannot_be_written(self) -> None:
        # The entity name comes from the URL; without an allow-list a crafted
        # path could reach any table in the schema.
        self.assertEqual(self.post("/profile/wombat/add", title="x")[0], 404)

    def test_an_unknown_entity_cannot_be_deleted(self) -> None:
        self.assertEqual(self.post("/profile/sqlite_master/1/delete")[0], 404)

    def test_mutations_need_the_token(self) -> None:
        status, _ = self.app.post("/profile/experience/add", {"title": "x"})
        self.assertEqual(status, 403)

    def test_deleting_a_missing_row_is_a_404_not_a_crash(self) -> None:
        self.assertEqual(self.post("/profile/experience/999/delete")[0], 404)


class DeletionTests(BuilderTestCase):
    def test_deleting_a_position_removes_its_accomplishments(self) -> None:
        exp_id = self.add_position()
        self.post("/profile/achievement/add", experience_id=str(exp_id), title="Did a thing")
        self.assertEqual(self.post(f"/profile/experience/{exp_id}/delete")[0], 303)
        conn = sqlite3.connect(self.db_path)
        left = conn.execute("SELECT COUNT(*) FROM achievements").fetchone()[0]
        conn.close()
        self.assertEqual(left, 0)


class EndToEndTests(BuilderTestCase):
    """Enter a history through HTTP only, then tailor against a posting."""

    POSTING = (
        "Senior Backend Engineer - Payments\n\n"
        "We need someone who has run high-throughput event pipelines and can "
        "reason about PostgreSQL under load. Kubernetes expected."
    )

    def test_a_web_entered_profile_produces_a_tailoring_plan(self) -> None:
        relevant = self.add_position(
            title="Senior Backend Engineer", org="Northwind",
            skills="Python, PostgreSQL, Kubernetes",
        )
        self.add_position(
            title="Frontend Designer", org="Bellweather",
            start="2016-01", end="2018-01", skills="Figma",
        )
        self.post(
            "/profile/achievement/add", experience_id=str(relevant),
            title="Rebuilt the payments pipeline",
            description="Replaced a batch job with an event-driven pipeline.",
            impact="cut settlement lag from 6 hours to 90 seconds",
            skills="Kubernetes",
        )

        conn = db.connect(self.db_path)
        plan = retrieval.build_plan(graph.ProfileGraph.load(conn), self.POSTING)
        conn.close()

        chosen = [p.node.title for p in plan.experiences]
        self.assertIn("Senior Backend Engineer", chosen)
        # The unrelated position is not padding for a backend role.
        self.assertNotIn("Frontend Designer", chosen)

        bullets = [b.row["title"] for p in plan.experiences for b in p.bullets]
        self.assertIn("Rebuilt the payments pipeline", bullets)

        # Only evidenced skills may be claimed, and Figma is not one this
        # posting should surface.
        self.assertIn("PostgreSQL", plan.skills)
        self.assertNotIn("Figma", plan.skills)
        self.assertGreater(plan.fit, 0)


if __name__ == "__main__":
    unittest.main()
