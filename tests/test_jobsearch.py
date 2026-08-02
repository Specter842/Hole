"""Test suite for the profile graph, retrieval, and ingestion.

Runs on the standard library alone, no API key needed:

    python -m unittest discover -s tests
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobsearch import cli, db, generate, graph, linking, matching, render, retrieval, verify  # noqa: E402
from jobsearch.ingest import documents as ingest_documents  # noqa: E402
from jobsearch.ingest import linkedin as ingest_linkedin  # noqa: E402

BACKEND_POSTING = """
Senior Backend Engineer, Payments
Requirements
- 5+ years designing and building high-throughput Python services
- Production experience with PostgreSQL and Redis at scale, including query tuning
- Docker, Kubernetes, and modern CI/CD
Nice to have
- Payments or fintech domain experience, PCI DSS compliance
"""

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class TempDbCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.db_path = self.tmp / "test.db"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def seed(self) -> dict[str, int]:
        """A small but complete graph: one position, bullets, a project, skills."""
        with db.session(self.db_path) as conn:
            db.set_profile_field(conn, "name", "Sam Rivera")
            db.set_profile_field(conn, "email", "sam@example.com")
            org = db.upsert_organization(conn, "Northwind Retail, Inc.", kind="company")
            experience_id = db.insert_row(
                conn,
                "experiences",
                {
                    "organization_id": org,
                    "title": "Senior Software Engineer",
                    "start_date": "2023-02",
                    "end_date": "2025-01",
                    "field": "software engineering",
                    "verified": 1,
                },
            )
            bullet_id = db.insert_row(
                conn,
                "achievements",
                {
                    "experience_id": experience_id,
                    "title": "Rebuilt the checkout API",
                    "description": "Event-driven Python service on PostgreSQL and Redis.",
                    "quantified_impact": "cut p95 latency from 1.9s to 380ms",
                    "verified": 1,
                },
            )
            db.link_skills_to(
                conn, ["Python", "PostgreSQL", "Redis"], "achievement", bullet_id, verified=1
            )
            project_id = db.insert_row(
                conn, "projects", {"name": "Raft key-value store", "description": "Go, consensus.", "verified": 1}
            )
            db.upsert_skill(conn, "Rust", verified=1)  # deliberately unevidenced
            return {"experience": experience_id, "achievement": bullet_id, "project": project_id}


# --------------------------------------------------------------------------- database


class DatabaseTests(TempDbCase):
    def test_organizations_deduplicate_on_suffix(self) -> None:
        with db.session(self.db_path) as conn:
            first = db.upsert_organization(conn, "Google LLC")
            second = db.upsert_organization(conn, "Google, Inc.")
            third = db.upsert_organization(conn, "google")
            self.assertEqual(first, second)
            self.assertEqual(second, third)
            self.assertEqual(db.count_rows(conn, "organizations"), 1)

    def test_organization_keeps_first_display_name(self) -> None:
        with db.session(self.db_path) as conn:
            org = db.upsert_organization(conn, "Northwind Retail")
            db.upsert_organization(conn, "northwind retail llc")
            self.assertEqual(db.get_row(conn, "organizations", org)["name"], "Northwind Retail")

    def test_skills_deduplicate_case_insensitively(self) -> None:
        with db.session(self.db_path) as conn:
            first = db.upsert_skill(conn, "PostgreSQL")
            second = db.upsert_skill(conn, "postgresql ")
            self.assertEqual(first, second)
            self.assertEqual(db.count_rows(conn, "skills"), 1)

    def test_skill_evidence_is_idempotent(self) -> None:
        ids = self.seed()
        with db.session(self.db_path) as conn:
            skill_id = db.upsert_skill(conn, "Python")
            before = db.count_rows(conn, "skill_evidence")
            db.add_skill_evidence(conn, skill_id, "achievement", ids["achievement"])
            self.assertEqual(db.count_rows(conn, "skill_evidence"), before)

    def test_achievement_requires_exactly_one_parent(self) -> None:
        ids = self.seed()
        with db.session(self.db_path) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                db.insert_row(conn, "achievements", {"title": "Orphan", "description": "x"})
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO achievements (experience_id, project_id, title, description) "
                    "VALUES (?, ?, 'Two parents', 'x')",
                    (ids["experience"], ids["project"]),
                )

    def test_deleting_a_position_removes_its_bullets(self) -> None:
        ids = self.seed()
        with db.session(self.db_path) as conn:
            db.delete_row(conn, "experiences", ids["experience"])
            self.assertEqual(db.list_achievements(conn, experience_id=ids["experience"]), [])

    def test_profile_aliases_resolve(self) -> None:
        with db.session(self.db_path) as conn:
            db.set_profile_field(conn, "name", "Sam Rivera")
            db.set_profile_field(conn, "linkedin", "in/sam")
            profile = db.get_profile(conn)
            self.assertEqual(profile["full_name"], "Sam Rivera")
            self.assertEqual(profile["linkedin_url"], "in/sam")

    def test_unknown_profile_keys_become_attributes(self) -> None:
        with db.session(self.db_path) as conn:
            db.set_profile_field(conn, "salary_floor", "150000")
            self.assertEqual(db.get_profile(conn)["salary_floor"], "150000")

    def test_unevidenced_skills_are_listed(self) -> None:
        self.seed()
        with db.session(self.db_path) as conn:
            self.assertEqual([s["name"] for s in db.unevidenced_skills(conn)], ["Rust"])

    def test_source_undo_removes_only_that_import(self) -> None:
        with db.session(self.db_path) as conn:
            source_id = db.create_source(conn, "document", label="resume.pdf")
            db.insert_row(conn, "experiences", {"title": "Kept", "verified": 1})
            db.insert_row(conn, "experiences", {"title": "Removed", "source_id": source_id})
            db.delete_source_rows(conn, source_id)
            titles = [row["title"] for row in db.list_experiences(conn)]
        self.assertEqual(titles, ["Kept"])


class MigrationTests(TempDbCase):
    V1_DDL = """
    CREATE TABLE achievements (
        id INTEGER PRIMARY KEY, field TEXT NOT NULL, title TEXT NOT NULL,
        description TEXT NOT NULL, quantified_impact TEXT, skills TEXT,
        employer TEXT, start_date TEXT, end_date TEXT);
    CREATE TABLE profile (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """

    def _make_v1(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.executescript(self.V1_DDL)
        conn.execute(
            "INSERT INTO achievements (field, title, description, quantified_impact, skills, "
            "employer, start_date, end_date) VALUES (?,?,?,?,?,?,?,?)",
            ("software engineering", "Rebuilt checkout", "Python service.", "cut latency 80%",
             '["python","redis"]', "Northwind Retail", "2023-02", "2025-01"),
        )
        conn.execute(
            "INSERT INTO achievements (field, title, description, employer, start_date, end_date) "
            "VALUES (?,?,?,?,?,?)",
            ("software engineering", "Owned CI/CD", "GitHub Actions.", "Northwind Retail",
             "2023-06", "2024-11"),
        )
        conn.execute(
            "INSERT INTO achievements (field, title, description, employer, end_date) VALUES (?,?,?,?,?)",
            ("education", "B.S. Computer Science", "Distributed systems.",
             "University of Texas at Austin", "2021-05"),
        )
        conn.execute("INSERT INTO profile VALUES ('name', 'Sam Rivera')")
        conn.commit()
        conn.close()

    def test_flat_table_becomes_a_graph(self) -> None:
        self._make_v1()
        with db.session(self.db_path) as conn:
            experiences = db.list_experiences(conn)
            education = db.list_education(conn)
            self.assertEqual(len(experiences), 1)  # both bullets share one employer+field
            self.assertEqual(experiences[0]["organization"], "Northwind Retail")
            self.assertEqual(len(db.list_achievements(conn, experience_id=experiences[0]["id"])), 2)
            self.assertEqual(len(education), 1)
            self.assertEqual(db.get_profile(conn)["full_name"], "Sam Rivera")

    def test_migration_preserves_skills_with_evidence(self) -> None:
        self._make_v1()
        with db.session(self.db_path) as conn:
            names = {s["name"]: s["evidence_count"] for s in db.list_skills(conn)}
        self.assertIn("python", names)
        self.assertGreater(names["python"], 0)

    def test_migration_is_idempotent(self) -> None:
        self._make_v1()
        with db.session(self.db_path) as conn:
            first = len(db.list_experiences(conn))
        with db.session(self.db_path) as conn:
            self.assertEqual(len(db.list_experiences(conn)), first)


# --------------------------------------------------------------------------- matching


class MatchingTests(unittest.TestCase):
    def doc(self, key: tuple[str, int], **fields: object) -> matching.MatchDoc:
        return matching.MatchDoc(key=key, label=str(key), fields=dict(fields))

    def test_stemmer_bridges_verb_forms(self) -> None:
        self.assertEqual(matching.tokenize("designed")[0], matching.tokenize("design")[0])
        self.assertEqual(matching.tokenize("building")[0], matching.tokenize("build")[0])
        self.assertEqual(matching.tokenize("shipped")[0], matching.tokenize("ship")[0])
        self.assertEqual(matching.tokenize("systems")[0], matching.tokenize("system")[0])

    def test_stemmer_leaves_short_words_alone(self) -> None:
        self.assertEqual(matching.tokenize("need")[0], "need")
        self.assertEqual(matching.tokenize("used")[0], "used")

    def test_stopwords_still_filter_after_stemming(self) -> None:
        # "having" stems to "hav"; the stopword set folds in both forms, so the
        # lookup still works on a stemmed token.
        self.assertIn("hav", matching.STOPWORDS)
        tokens = matching.content_tokens("having a plan")
        self.assertNotIn("hav", tokens)
        self.assertIn("plan", tokens)

    def test_boilerplate_filtering_survives_stemming(self) -> None:
        self.assertIn("includ", matching.BOILERPLATE)
        self.assertIn("including", matching.BOILERPLATE)
        doc = self.doc(("a", 1), text="Python.")
        gaps = matching.coverage_gaps("Requirements\n- Experience including query tuning\n", [doc])
        self.assertNotIn("including", " ".join(gaps))
        self.assertIn("query tuning", gaps)

    def test_phrases_stay_inside_a_clause(self) -> None:
        found = matching.phrases("services end to end, including query tuning")
        self.assertNotIn("end end", found)
        self.assertNotIn("end including", found)
        self.assertIn("query tun", found)

    def test_surface_forms_restore_the_original_wording(self) -> None:
        surfaces = matching.surface_forms("Experience with query tuning and Kubernetes")
        self.assertEqual(surfaces["query tun"], "query tuning")
        self.assertEqual(surfaces["kubernete"], "kubernetes")

    def test_relevant_record_outranks_irrelevant(self) -> None:
        backend = self.doc(("achievement", 1), tags=["python", "redis"], title="Checkout API",
                           text="Event-driven Python service on PostgreSQL.")
        marketing = self.doc(("achievement", 2), tags=["copywriting"], title="Newsletter",
                             text="Wrote a biweekly newsletter.")
        matches = matching.score_records(BACKEND_POSTING, [marketing, backend])
        self.assertEqual(matches[0].doc.key, ("achievement", 1))
        self.assertEqual(matches[0].relative, 100.0)
        self.assertGreater(matches[0].score, matches[1].score)

    def test_tags_outweigh_prose(self) -> None:
        tagged = self.doc(("a", 1), tags=["kubernetes"])
        mentioned = self.doc(("a", 2), text="we also touched kubernetes once")
        matches = matching.score_records(BACKEND_POSTING, [tagged, mentioned])
        self.assertEqual(matches[0].doc.key, ("a", 1))

    def test_empty_input_scores_nothing(self) -> None:
        self.assertEqual(matching.score_records(BACKEND_POSTING, []), [])

    def test_coverage_gaps_report_real_holes_in_the_postings_words(self) -> None:
        doc = self.doc(("a", 1), tags=["python", "postgresql"], text="Python service on PostgreSQL.")
        gaps = matching.coverage_gaps(BACKEND_POSTING, [doc])
        # Exact membership: gaps are rendered in the posting's own words.
        self.assertIn("payments", gaps)
        self.assertIn("pci dss", gaps)
        self.assertIn("query tuning", gaps)
        self.assertNotIn("query tun", gaps)  # the stemmed form never reaches the report
        self.assertNotIn("python", " ".join(gaps))

    def test_company_name_is_not_a_gap(self) -> None:
        posting = BACKEND_POSTING + "\nAbout Meridian\nMeridian builds infrastructure.\n"
        doc = self.doc(("a", 1), text="Python.")
        self.assertNotIn("meridian", " ".join(matching.coverage_gaps(posting, [doc], company="Meridian")))

    def test_fit_score_rises_with_coverage(self) -> None:
        weak = self.doc(("a", 1), text="I wrote a newsletter.")
        strong = self.doc(
            ("a", 2),
            tags=["python", "postgresql", "redis", "docker", "kubernetes", "ci/cd"],
            text="High-throughput Python services, PostgreSQL query tuning, payments and PCI DSS.",
        )
        low = matching.fit_score(BACKEND_POSTING, [weak])
        high = matching.fit_score(BACKEND_POSTING, [strong])
        self.assertLess(low, 20.0)
        self.assertGreater(high, low)
        self.assertLessEqual(high, 100.0)

    def test_claimlike_keeps_names_and_drops_ordinary_words(self) -> None:
        posting = (
            "Senior Backend Engineer, Payments Platform\n"
            "- Familiarity with Terraform and AWS\n"
            "- 5+ years building backend services on the payments platform\n"
            "- Exposure to PCI DSS compliance\n"
        )
        kept = matching.claimlike_terms(
            posting, ["terraform", "pci dss", "backend", "platform", "ci/cd"]
        )
        self.assertIn("terraform", kept)   # capitalized mid-sentence
        self.assertIn("pci dss", kept)     # multi-word phrase
        self.assertIn("ci/cd", kept)       # non-alphabetic, clearly a technology
        self.assertNotIn("backend", kept)  # only ever a heading or lowercase
        self.assertNotIn("platform", kept)

    def test_heading_lines_do_not_prove_a_term_is_a_name(self) -> None:
        self.assertTrue(matching._is_heading_line("Senior Backend Engineer, Payments Platform"))
        self.assertTrue(matching._is_heading_line("Nice to Have"))
        self.assertFalse(matching._is_heading_line("- Familiarity with Terraform and AWS"))
        self.assertFalse(
            matching._is_heading_line("We are building the payments platform that powers checkout")
        )

    def test_phrase_counts_as_covered_when_both_halves_are(self) -> None:
        self.assertTrue(matching._covers("python service", {"python", "service"}))
        self.assertFalse(matching._covers("pci dss", {"pci"}))


# --------------------------------------------------------------------------- graph


class GraphTests(TempDbCase):
    def test_load_attaches_bullets_to_their_position(self) -> None:
        ids = self.seed()
        with db.session(self.db_path) as conn:
            g = graph.ProfileGraph.load(conn)
        self.assertEqual(len(g.experiences), 1)
        self.assertEqual(len(g.experiences[0].achievements), 1)
        self.assertEqual(g.experiences[0].achievements[0].id, ids["achievement"])
        self.assertEqual(g.experiences[0].organization, "Northwind Retail, Inc.")

    def test_experience_match_doc_absorbs_bullet_text(self) -> None:
        self.seed()
        with db.session(self.db_path) as conn:
            g = graph.ProfileGraph.load(conn)
        text = g.experiences[0].match_doc().fields["text"]
        self.assertIn("PostgreSQL", text)  # comes from the bullet, not the position row

    def test_evidenced_skills_exclude_naked_ones(self) -> None:
        self.seed()
        with db.session(self.db_path) as conn:
            g = graph.ProfileGraph.load(conn)
        names = {s["name"] for s in g.evidenced_skills}
        self.assertIn("Python", names)
        self.assertNotIn("Rust", names)

    def test_counts_and_emptiness(self) -> None:
        with db.session(self.db_path) as conn:
            self.assertTrue(graph.ProfileGraph.load(conn).is_empty())
        self.seed()
        with db.session(self.db_path) as conn:
            g = graph.ProfileGraph.load(conn)
        self.assertFalse(g.is_empty())
        self.assertEqual(g.counts()["accomplishments"], 1)

    def test_date_range_marks_current_roles(self) -> None:
        self.assertEqual(graph.date_range("2023-02", None), "2023-02 - Present")
        self.assertEqual(graph.date_range("2023-02", "2025-01"), "2023-02 - 2025-01")
        self.assertEqual(graph.date_range(None, None), "")


# --------------------------------------------------------------------------- retrieval


class RetrievalTests(TempDbCase):
    def plan(self, **kwargs: object) -> retrieval.ResumePlan:
        with db.session(self.db_path) as conn:
            g = graph.ProfileGraph.load(conn)
        return retrieval.build_plan(g, BACKEND_POSTING, company="Meridian", **kwargs)

    def test_plan_selects_the_matching_position_and_bullets(self) -> None:
        self.seed()
        plan = self.plan()
        self.assertEqual(len(plan.experiences), 1)
        self.assertEqual(plan.experiences[0].node.title, "Senior Software Engineer")
        self.assertEqual(len(plan.experiences[0].bullets), 1)

    def test_unevidenced_skill_never_reaches_the_plan(self) -> None:
        self.seed()
        plan = self.plan()
        self.assertNotIn("Rust", plan.skills)
        self.assertNotIn("Rust", plan.other_skills + plan.skills)

    def test_only_evidenced_and_relevant_skills_are_claimable(self) -> None:
        self.seed()
        plan = self.plan()
        self.assertIn("Python", plan.skills)
        self.assertIn("PostgreSQL", plan.skills)

    def test_gaps_and_unevidenced_requests_are_reported(self) -> None:
        self.seed()
        plan = self.plan()
        self.assertTrue(plan.gaps)
        joined = " ".join(plan.unevidenced_requests)
        self.assertIn("pci dss", joined)

    def test_facts_payload_is_the_closed_fact_set(self) -> None:
        self.seed()
        facts = self.plan().to_facts()
        self.assertEqual(
            set(facts),
            {
                "candidate_profile", "target", "fit_score", "skills_you_may_claim",
                "other_evidenced_skills", "experience", "projects", "education",
                "certifications", "posting_requirements_with_no_supporting_record",
                "skills_the_posting_wants_that_you_cannot_evidence",
            },
        )
        self.assertEqual(facts["experience"][0]["organization"], "Northwind Retail, Inc.")

    def test_missing_profile_fields_are_flagged(self) -> None:
        with db.session(self.db_path) as conn:
            db.insert_row(conn, "experiences", {"title": "Engineer", "verified": 1})
        plan = self.plan()
        self.assertIn("full_name", plan.missing_profile_fields)

    def test_verified_only_excludes_unconfirmed_rows(self) -> None:
        self.seed()
        with db.session(self.db_path) as conn:
            db.insert_row(conn, "experiences", {"title": "Python Contractor", "verified": 0})
        titles = {p.node.title for p in self.plan(verified_only=True).experiences}
        self.assertNotIn("Python Contractor", titles)

    def test_recent_position_is_kept_for_timeline_continuity(self) -> None:
        with db.session(self.db_path) as conn:
            db.insert_row(
                conn,
                "experiences",
                {"title": "Barista", "start_date": "2025-02", "is_current": 1, "verified": 1},
            )
            experience_id = db.insert_row(
                conn,
                "experiences",
                {"title": "Python Engineer", "start_date": "2023-01", "end_date": "2025-01", "verified": 1},
            )
            db.link_skills_to(conn, ["Python", "Redis"], "experience", experience_id, verified=1)
        titles = {p.node.title: p for p in self.plan().experiences}
        self.assertIn("Barista", titles)
        self.assertTrue(titles["Barista"].kept_for_continuity)
        self.assertFalse(titles["Python Engineer"].kept_for_continuity)


# --------------------------------------------------------------------------- ingestion


class LinkedInImportTests(TempDbCase):
    def test_date_parsing(self) -> None:
        self.assertEqual(ingest_linkedin.parse_linkedin_date("Mar 2023"), "2023-03")
        self.assertEqual(ingest_linkedin.parse_linkedin_date("Jan 5, 2023"), "2023-01-05")
        self.assertEqual(ingest_linkedin.parse_linkedin_date("2021"), "2021")
        self.assertIsNone(ingest_linkedin.parse_linkedin_date(""))
        self.assertIsNone(ingest_linkedin.parse_linkedin_date("Present"))

    def test_bullet_splitting_leaves_prose_alone(self) -> None:
        self.assertEqual(
            ingest_linkedin.split_bullets("- Did a thing\n- Did another thing"),
            ["Did a thing", "Did another thing"],
        )
        self.assertEqual(ingest_linkedin.split_bullets("A single paragraph about my job."), [])

    def test_column_lookup_is_forgiving(self) -> None:
        row = {"Company Name": "Acme", "Started On": "Mar 2023"}
        self.assertEqual(ingest_linkedin.pick(row, "company name"), "Acme")
        self.assertEqual(ingest_linkedin.pick(row, "Company", "Company Name"), "Acme")
        self.assertIsNone(ingest_linkedin.pick(row, "Missing"))

    def test_import_demo_export_folder(self) -> None:
        if not (EXAMPLES / "demo_linkedin_export").is_dir():
            self.skipTest("demo export not present")
        with db.session(self.db_path) as conn:
            report = ingest_linkedin.import_archive(conn, EXAMPLES / "demo_linkedin_export")
            self.assertEqual(report.created["experiences"], 2)
            self.assertGreaterEqual(report.created["accomplishments"], 6)
            self.assertEqual(db.get_profile(conn)["full_name"], "Sam Rivera")
            self.assertEqual(db.get_profile(conn)["email"], "sam.rivera@example.com")

    def test_import_from_zip(self) -> None:
        archive_path = self.tmp / "export.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr(
                "Positions.csv",
                "Company Name,Title,Description,Location,Started On,Finished On\n"
                "Acme,Engineer,Built things.,Remote,Mar 2023,\n",
            )
            archive.writestr("Skills.csv", "Name\nPython\n")
        with db.session(self.db_path) as conn:
            report = ingest_linkedin.import_archive(conn, archive_path)
            experiences = db.list_experiences(conn)
        self.assertEqual(report.created["experiences"], 1)
        self.assertEqual(experiences[0]["is_current"], 1)  # no end date means current

    def test_linkedin_skills_arrive_without_evidence(self) -> None:
        archive_path = self.tmp / "export"
        archive_path.mkdir()
        (archive_path / "Skills.csv").write_text("Name\nKubernetes\n", encoding="utf-8")
        with db.session(self.db_path) as conn:
            ingest_linkedin.import_archive(conn, archive_path)
            self.assertEqual([s["name"] for s in db.unevidenced_skills(conn)], ["Kubernetes"])


class DocumentImportTests(TempDbCase):
    def test_json_response_survives_a_markdown_fence(self) -> None:
        parsed = ingest_documents.parse_json_response('```json\n{"skills": ["Go"]}\n```')
        self.assertEqual(parsed["skills"], ["Go"])
        self.assertEqual(ingest_documents.parse_json_response('{"a": 1}')["a"], 1)

    def test_bad_json_raises(self) -> None:
        with self.assertRaises(ValueError):
            ingest_documents.parse_json_response("no json here")

    def test_text_extraction(self) -> None:
        path = self.tmp / "notes.md"
        path.write_text("# Resume\nDid things.", encoding="utf-8")
        self.assertIn("Did things", ingest_documents.extract_text(path))

    def test_unsupported_suffix_is_rejected(self) -> None:
        path = self.tmp / "photo.jpeg"
        path.write_bytes(b"\x00\x01")
        with self.assertRaises(ValueError):
            ingest_documents.extract_text(path)

    def test_merge_lands_unverified_and_traceable(self) -> None:
        payload = {
            "profile": {"full_name": "Sam Rivera", "email": "sam@example.com"},
            "experiences": [
                {
                    "title": "Engineer",
                    "organization": "Acme",
                    "start_date": "2023-02",
                    "skills": ["Python"],
                    "accomplishments": [
                        {"title": "Shipped", "description": "Shipped the thing.",
                         "quantified_impact": "cut latency 40%", "skills": ["Redis"]}
                    ],
                }
            ],
            "certifications": [{"name": "AWS SAA", "issuer": "AWS"}],
            "skills": ["Terraform"],
        }
        with db.session(self.db_path) as conn:
            source_id = db.create_source(conn, "document", label="resume.pdf")
            report = ingest_documents.DocumentReport(source_id=source_id, path="resume.pdf")
            ingest_documents.merge_entities(conn, payload, source_id, report)
            experiences = db.list_experiences(conn)
            achievements = db.list_achievements(conn)
            self.assertEqual(experiences[0]["verified"], 0)
            self.assertEqual(experiences[0]["source_id"], source_id)
            self.assertEqual(achievements[0]["quantified_impact"], "cut latency 40%")
            self.assertEqual(db.get_profile(conn)["full_name"], "Sam Rivera")

    def test_merge_does_not_overwrite_an_existing_profile_field(self) -> None:
        with db.session(self.db_path) as conn:
            db.set_profile_field(conn, "full_name", "Samantha Rivera")
            source_id = db.create_source(conn, "document")
            report = ingest_documents.DocumentReport(source_id=source_id, path="x")
            ingest_documents.merge_entities(
                conn, {"profile": {"full_name": "S. Rivera"}}, source_id, report
            )
            self.assertEqual(db.get_profile(conn)["full_name"], "Samantha Rivera")

    def test_malformed_entries_are_skipped_not_crashed(self) -> None:
        payload = {"experiences": [None, {}, {"title": "Real"}], "skills": [None, "", "Go"]}
        with db.session(self.db_path) as conn:
            source_id = db.create_source(conn, "document")
            report = ingest_documents.DocumentReport(source_id=source_id, path="x")
            ingest_documents.merge_entities(conn, payload, source_id, report)
            self.assertEqual([e["title"] for e in db.list_experiences(conn)], ["Real"])


class LinkingTests(TempDbCase):
    def test_autolink_connects_named_skills(self) -> None:
        with db.session(self.db_path) as conn:
            db.insert_row(
                conn,
                "experiences",
                {"title": "Engineer", "description": "Ran Kubernetes and PostgreSQL in production."},
            )
            db.upsert_skill(conn, "Kubernetes")
            db.upsert_skill(conn, "PostgreSQL")
            db.upsert_skill(conn, "Rust")
            created = linking.autolink_skills(conn, commit=False)
            linked = {link.skill_name for link in created}
            self.assertEqual(linked, {"Kubernetes", "PostgreSQL"})
            self.assertEqual([s["name"] for s in db.unevidenced_skills(conn)], ["Rust"])

    def test_autolink_is_idempotent(self) -> None:
        with db.session(self.db_path) as conn:
            db.insert_row(conn, "experiences", {"title": "Engineer", "description": "Python."})
            db.upsert_skill(conn, "Python")
            self.assertEqual(len(linking.autolink_skills(conn, commit=False)), 1)
            self.assertEqual(linking.autolink_skills(conn, commit=False), [])

    def test_short_skill_names_do_not_match_everything(self) -> None:
        with db.session(self.db_path) as conn:
            db.insert_row(
                conn, "experiences", {"title": "Engineer", "description": "Rewrote the ingest layer."}
            )
            db.upsert_skill(conn, "R")
            db.upsert_skill(conn, "Go")
            self.assertEqual(linking.autolink_skills(conn, commit=False), [])

    def test_skill_inside_a_word_is_not_a_match(self) -> None:
        with db.session(self.db_path) as conn:
            db.insert_row(conn, "experiences", {"title": "Engineer", "description": "Used Javascript."})
            db.upsert_skill(conn, "Java")
            self.assertEqual(linking.autolink_skills(conn, commit=False), [])


# --------------------------------------------------------------------------- generation guards


class GenerationTests(unittest.TestCase):
    def test_parse_response_splits_three_sections(self) -> None:
        raw = ("===RESUME===\n# Sam\nBullet\n===COVER_LETTER===\nDear team,\n"
               "===FIT_NOTES===\nWeak on payments.\n")
        resume, letter, notes = generate.parse_response(raw)
        self.assertIn("# Sam", resume)
        self.assertNotIn("Dear team", resume)
        self.assertIn("Dear team", letter)
        self.assertIn("Weak on payments", notes)

    def test_parse_response_keeps_unmarked_output(self) -> None:
        resume, letter, notes = generate.parse_response("no markers here")
        self.assertEqual(resume, "no markers here")
        self.assertEqual((letter, notes), ("", ""))

    def test_user_message_carries_posting_and_plan(self) -> None:
        message = generate.build_user_message(BACKEND_POSTING, {"experience": [{"title": "Engineer"}]})
        self.assertIn("Senior Backend Engineer", message)
        self.assertIn("Engineer", message)
        self.assertIn("complete set of facts", message)

    def test_system_prompt_states_the_hard_rules(self) -> None:
        self.assertIn("Never invent employers", generate.SYSTEM_PROMPT)
        self.assertIn("closed list", generate.SYSTEM_PROMPT)

    def test_generate_refuses_an_empty_plan(self) -> None:
        class Empty:
            def is_empty(self) -> bool:
                return True

        with self.assertRaises(generate.GenerationError):
            generate.generate("posting", Empty())

    def test_slugify(self) -> None:
        self.assertEqual(generate.slugify("Meridian Systems!", "x"), "meridian-systems")
        self.assertEqual(generate.slugify(None, "role"), "role")


class VerifyTests(unittest.TestCase):
    FACTS = {
        "candidate_profile": {"full_name": "Sam Rivera"},
        "experience": [
            {
                "organization": "Northwind Retail",
                "title": "Senior Software Engineer",
                "accomplishments": [
                    {"description": "Rebuilt checkout.", "quantified_impact": "cut p95 to 380ms"}
                ],
            }
        ],
        "skills_the_posting_wants_that_you_cannot_evidence": ["pci dss", "terraform"],
    }

    def test_sourced_metric_passes(self) -> None:
        self.assertEqual(verify.verify_plan({"resume": "Cut p95 to 380ms."}, self.FACTS), [])

    def test_invented_metric_is_flagged(self) -> None:
        findings = verify.verify_plan({"resume": "Saved $4.2M annually."}, self.FACTS)
        self.assertEqual([f.kind for f in findings], ["unsourced-number"])

    def test_unknown_employer_is_flagged(self) -> None:
        findings = verify.verify_plan({"resume": "Led a team at Globex Technologies."}, self.FACTS)
        self.assertEqual([f.value for f in findings], ["Globex Technologies"])

    def test_known_employer_and_target_pass(self) -> None:
        text = "Worked at Northwind Retail. Excited about Meridian Systems."
        findings = verify.verify_plan({"resume": text}, self.FACTS, target_company="Meridian Systems")
        self.assertEqual(findings, [])

    def test_forbidden_skill_in_the_draft_is_caught(self) -> None:
        findings = verify.verify_plan({"resume": "Deep PCI DSS compliance experience."}, self.FACTS)
        self.assertEqual([f.kind for f in findings], ["unevidenced-claim"])
        self.assertEqual(findings[0].value, "pci dss")

    def test_placeholder_is_caught(self) -> None:
        findings = verify.verify_plan({"cover_letter": "Sincerely, [Your Name]"}, self.FACTS)
        self.assertEqual([f.kind for f in findings], ["placeholder"])
        self.assertIn("cover_letter:", findings[0].context)


class RenderTests(unittest.TestCase):
    def test_markdown_subset(self) -> None:
        body = render.markdown_to_html_body(
            "# Sam Rivera\n\n## Experience\n\n- **Built** things\n- Shipped [docs](http://x.io)\n"
        )
        self.assertIn("<h1>Sam Rivera</h1>", body)
        self.assertIn("<strong>Built</strong>", body)
        self.assertIn('<a href="http://x.io">docs</a>', body)
        self.assertEqual(body.count("<ul>"), 1)
        self.assertEqual(body.count("</ul>"), 1)

    def test_html_is_escaped(self) -> None:
        body = render.markdown_to_html_body("Scaled A & B <script>alert(1)</script>")
        self.assertNotIn("<script>", body)
        self.assertIn("&amp;", body)

    def test_full_document_has_print_css(self) -> None:
        doc = render.markdown_to_html("# Hi", "Resume")
        self.assertIn("<title>Resume</title>", doc)
        self.assertIn("@page", doc)


# --------------------------------------------------------------------------- CLI


class CliTests(TempDbCase):
    def run_cli(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main([*argv, "--db", str(self.db_path)])
        return code, buffer.getvalue()

    def test_init_reports_an_empty_profile(self) -> None:
        code, output = self.run_cli("init")
        self.assertEqual(code, 0)
        self.assertIn("import linkedin", output)

    def test_import_link_profile_flow(self) -> None:
        if not (EXAMPLES / "demo_linkedin_export").is_dir():
            self.skipTest("demo export not present")
        code, output = self.run_cli("import", "linkedin", str(EXAMPLES / "demo_linkedin_export"))
        self.assertEqual(code, 0)
        self.assertIn("experiences", output)

        code, output = self.run_cli("link")
        self.assertEqual(code, 0)
        self.assertIn("Python", output)

        code, output = self.run_cli("profile")
        self.assertEqual(code, 0)
        self.assertIn("Sam Rivera", output)
        self.assertIn("Northwind Retail", output)
        self.assertIn("never reach a resume", output)  # unevidenced skills surfaced

    def test_match_reports_the_plan(self) -> None:
        self.seed()
        posting = self.tmp / "posting.txt"
        posting.write_text(BACKEND_POSTING, encoding="utf-8")
        code, output = self.run_cli("match", "--job-file", str(posting))
        self.assertEqual(code, 0)
        self.assertIn("Fit score", output)
        self.assertIn("Senior Software Engineer", output)
        self.assertIn("NOT evidenced", output)

    def test_match_on_an_empty_graph_fails_loudly(self) -> None:
        posting = self.tmp / "posting.txt"
        posting.write_text(BACKEND_POSTING, encoding="utf-8")
        self.assertEqual(self.run_cli("match", "--job-file", str(posting))[0], 1)

    def test_tailor_dry_run_makes_no_api_call(self) -> None:
        self.seed()
        posting = self.tmp / "posting.txt"
        posting.write_text(BACKEND_POSTING, encoding="utf-8")
        code, output = self.run_cli("tailor", "--job-file", str(posting), "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("DRY RUN", output)
        self.assertIn("Never invent employers", output)
        with db.session(self.db_path) as conn:
            self.assertEqual(db.list_applications(conn), [])

    def test_add_and_list_records(self) -> None:
        code, _ = self.run_cli(
            "add", "experience", "--title", "Engineer", "--org", "Acme",
            "--skills", "python,redis", "--start", "2023-01",
        )
        self.assertEqual(code, 0)
        code, output = self.run_cli("list", "experiences")
        self.assertIn("Engineer - Acme", output)

        code, output = self.run_cli(
            "add", "achievement", "--experience", "1", "--title", "Shipped",
            "--description", "Shipped the thing.", "--impact", "cut latency 40%",
        )
        self.assertEqual(code, 0)
        code, output = self.run_cli("show", "experiences", "1")
        self.assertIn("Shipped the thing.", output)

    def test_achievement_needs_exactly_one_parent(self) -> None:
        self.seed()
        code, _ = self.run_cli("add", "achievement", "--title", "x", "--description", "y")
        self.assertEqual(code, 1)

    def test_skill_evidence_gate_via_cli(self) -> None:
        ids = self.seed()
        code, output = self.run_cli("skill", "add", "Terraform")
        self.assertEqual(code, 0)
        self.assertIn("cannot appear on a resume", output)
        code, _ = self.run_cli(
            "skill", "evidence", "Terraform", "experience", str(ids["experience"])
        )
        self.assertEqual(code, 0)
        with db.session(self.db_path) as conn:
            self.assertNotIn("Terraform", [s["name"] for s in db.unevidenced_skills(conn)])

    def test_review_lists_and_confirms_unverified_rows(self) -> None:
        with db.session(self.db_path) as conn:
            source_id = db.create_source(conn, "document", label="resume.pdf")
            db.insert_row(conn, "experiences", {"title": "Extracted", "source_id": source_id})
        code, output = self.run_cli("review")
        self.assertEqual(code, 0)
        self.assertIn("Extracted", output)
        code, _ = self.run_cli("review", "confirm", "experiences")
        self.assertEqual(code, 0)
        code, output = self.run_cli("review")
        self.assertIn("Nothing awaiting review", output)

    def test_sources_undo(self) -> None:
        with db.session(self.db_path) as conn:
            source_id = db.create_source(conn, "document", label="bad.pdf")
            db.insert_row(conn, "experiences", {"title": "Wrong", "source_id": source_id})
        code, output = self.run_cli("sources")
        self.assertIn("bad.pdf", output)
        code, _ = self.run_cli("sources", "undo", str(source_id), "--yes")
        self.assertEqual(code, 0)
        with db.session(self.db_path) as conn:
            self.assertEqual(db.list_experiences(conn), [])

    def test_application_status_gate(self) -> None:
        with db.session(self.db_path) as conn:
            db.insert_application(conn, {"company": "Meridian", "role": "SBE", "fit_score": 61.0})
        self.assertEqual(self.run_cli("apps", "status", "1", "not-a-status")[0], 1)
        code, output = self.run_cli("apps", "status", "1", "approved")
        self.assertEqual(code, 0)
        self.assertIn("drafted -> approved", output)
        with db.session(self.db_path) as conn:
            self.assertIsNotNone(db.get_application(conn, 1)["approved_at"])
        self.run_cli("apps", "status", "1", "sent")
        with db.session(self.db_path) as conn:
            self.assertIsNotNone(db.get_application(conn, 1)["sent_date"])


if __name__ == "__main__":
    unittest.main()
