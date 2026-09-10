"""Integration test for the full Greenhouse collection flow.

configuration -> GreenhouseProvider -> mock Greenhouse API -> normalization
-> deduplication/upsert -> database -> stored Job

The Greenhouse HTTP API is mocked (never called for real). The database
layer is the project's real MySQL connection (the same one app.py uses),
because this project has no DB-mocking/sqlite test harness — every other
existing test in this module avoids the database entirely rather than
faking it. This test is skipped, not failed, when that database is not
reachable (e.g. a CI runner with no MySQL configured), and it cleans up
every row it creates.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from job_agent.db import get_db, init_job_tables


TEST_BOARD_ID = "digidara-integration-test-board"
TEST_COMPANY_NAME = "DigiDARA Integration Test Co"
TEST_SOURCE_NAME = f"greenhouse:{TEST_BOARD_ID}"


def _mysql_available():
    try:
        db = get_db()
        db.close()
        return True
    except Exception:
        return False


def _sample_raw_jobs():
    return [
        {
            "id": 555001,
            "title": "Integration Test Engineer",
            "absolute_url": "https://boards.greenhouse.io/digidara-integration-test-board/jobs/555001",
            "location": {"name": "Chennai, Tamil Nadu, India"},
            "departments": [{"name": "Engineering"}],
            "offices": [{"name": "Chennai"}],
            "metadata": [{"name": "Employment Type", "value": "Full-time"}],
            "content": "<p>Verify the Greenhouse integration end to end.</p>",
            "first_published": "2026-08-01T00:00:00Z",
            "updated_at": "2026-08-20T00:00:00Z",
        }
    ]


@unittest.skipUnless(_mysql_available(), "MySQL database is not reachable in this environment")
class GreenhouseIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_job_tables()

    def tearDown(self):
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "DELETE FROM jobs WHERE source_id IN (SELECT id FROM job_sources WHERE name=%s)",
                (TEST_SOURCE_NAME,),
            )
            cursor.execute(
                "DELETE FROM job_ingestion_runs WHERE source_id IN (SELECT id FROM job_sources WHERE name=%s)",
                (TEST_SOURCE_NAME,),
            )
            cursor.execute("DELETE FROM job_sources WHERE name=%s", (TEST_SOURCE_NAME,))
            db.commit()
        finally:
            cursor.close()
            db.close()

    def _config(self):
        # Include the real, currently configured companies alongside the
        # synthetic test one: sync_greenhouse_sources() reconciles the
        # entire shared job_sources table against this config and disables
        # every row not named in it, so a config containing only the test
        # company would disable every real company's row as a side effect.
        from job_agent.providers.config_loader import get_greenhouse_companies

        real_companies = [dict(company, enabled=True) for company in get_greenhouse_companies()]
        return {
            "greenhouse": {
                "enabled": True,
                "companies": real_companies + [{"name": TEST_COMPANY_NAME, "board_id": TEST_BOARD_ID, "enabled": True}],
            }
        }

    def test_config_to_database_end_to_end(self):
        from job_agent.providers.sync import sync_greenhouse_sources

        config = self._config()
        expected_count = len(config["greenhouse"]["companies"])  # real companies + this test's own
        with patch("jobs.providers.config_loader.load_providers_config", return_value=config):
            synced = sync_greenhouse_sources()
        self.assertEqual(synced, expected_count)

        db = get_db()
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM job_sources WHERE name=%s", (TEST_SOURCE_NAME,))
            source = cursor.fetchone()
        finally:
            cursor.close()
            db.close()
        self.assertIsNotNone(source)
        self.assertEqual(source["source_type"], "greenhouse")
        self.assertTrue(source["is_active"])
        self.assertTrue(source["scraping_authorized"])

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"{}"
        mock_response.json.return_value = {"jobs": _sample_raw_jobs(), "meta": {}}
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response

        with patch("jobs.providers.greenhouse.requests.Session", return_value=mock_session):
            from job_agent.service import process_run, queue_source_run

            run_id = queue_source_run(source["id"], admin_id=None)
            result = process_run(run_id)

        self.assertEqual(result["fetched"], 1)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["updated"], 0)

        db = get_db()
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT * FROM jobs WHERE source_id=%s AND external_id=%s",
                (source["id"], "555001"),
            )
            job = cursor.fetchone()
        finally:
            cursor.close()
            db.close()

        self.assertIsNotNone(job)
        self.assertEqual(job["title"], "Integration Test Engineer")
        self.assertEqual(job["company"], TEST_COMPANY_NAME)
        self.assertEqual(job["department"], "Engineering")
        self.assertEqual(job["employment_type"], "Full-time")
        self.assertEqual(job["apply_url"], _sample_raw_jobs()[0]["absolute_url"])
        self.assertEqual(job["status"], "pending")

        # Running the same board again must not create a duplicate row.
        with patch("jobs.providers.greenhouse.requests.Session", return_value=mock_session):
            run_id_2 = queue_source_run(source["id"], admin_id=None)
            result_2 = process_run(run_id_2)
        self.assertEqual(result_2["inserted"], 0)

        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM jobs WHERE source_id=%s AND external_id=%s",
                (source["id"], "555001"),
            )
            count = cursor.fetchone()[0]
        finally:
            cursor.close()
            db.close()
        self.assertEqual(count, 1)

    def test_partial_failure_across_companies(self):
        from job_agent.providers import sync as sync_module
        from job_agent.providers.config_loader import get_greenhouse_companies

        # sync_greenhouse_sources() (called internally by
        # run_greenhouse_collection()) reconciles the ENTIRE shared
        # job_sources table against whatever config it's given - it
        # disables every row not named in that config. A mocked config
        # containing only this test's 3 synthetic companies would
        # therefore disable every real Greenhouse company's row as a side
        # effect. Including the real, currently configured companies here
        # (read live, not hardcoded) keeps this test scoped to its own
        # synthetic boards only.
        real_companies = [dict(company, enabled=True) for company in get_greenhouse_companies()]
        config = {
            "greenhouse": {
                "enabled": True,
                "companies": real_companies + [
                    {"name": "Good Co A", "board_id": f"{TEST_BOARD_ID}-a", "enabled": True},
                    {"name": "Bad Co B", "board_id": f"{TEST_BOARD_ID}-b", "enabled": True},
                    {"name": "Good Co C", "board_id": f"{TEST_BOARD_ID}-c", "enabled": True},
                ],
            }
        }

        def fake_fetch_and_normalize(board_id, company_name, session=None):
            from job_agent.providers.greenhouse import NormalizedJobs

            if not board_id.startswith(TEST_BOARD_ID):
                # A real company's board, swept in because the config
                # above (correctly) includes every real company alongside
                # the synthetic ones. Return no jobs rather than either
                # making a live HTTP call (tests must not depend on live
                # Greenhouse services) or inserting a fake job against a
                # real company's source. raw_count=1 (not 0) so a company
                # with no stored jobs yet is left as NO_MATCHING_JOBS
                # rather than being mischaracterized as EMPTY_BOARD - this
                # fake can't know each real board's true published count,
                # and every currently configured company does have at
                # least one published job, so 1 is the closer default. A
                # company with jobs already on file is unaffected either
                # way (status is decided from the stored count first).
                return NormalizedJobs([], raw_count=1)
            if board_id.endswith("-b"):
                from job_agent.providers.greenhouse import GreenhouseAPIError

                raise GreenhouseAPIError("simulated API failure for company B")
            return [
                {
                    "external_id": f"job-{board_id}",
                    "title": f"Engineer at {company_name}",
                    "company": company_name,
                    "location": "Chennai",
                    "work_mode": "onsite",
                    "employment_type": "Full-time",
                    "department": "Engineering",
                    "salary_text": "",
                    "description": "Sample role",
                    "skills": [],
                    "apply_url": f"https://boards.greenhouse.io/{board_id}/jobs/1",
                    "source_url": f"https://boards.greenhouse.io/{board_id}/jobs/1",
                    "published_at": None,
                    "expires_at": None,
                }
            ]

        try:
            with patch("jobs.providers.config_loader.load_providers_config", return_value=config), \
                 patch("jobs.providers.greenhouse.fetch_and_normalize", side_effect=fake_fetch_and_normalize):
                result = sync_module.run_greenhouse_collection()

            self.assertEqual(result["totals"]["failed_companies"], 1)
            self.assertEqual(result["totals"]["inserted"], 2)
            statuses = {c["board_id"]: c["status"] for c in result["companies"]}
            self.assertEqual(statuses[f"{TEST_BOARD_ID}-a"], "success")
            self.assertEqual(statuses[f"{TEST_BOARD_ID}-b"], "failed")
            self.assertEqual(statuses[f"{TEST_BOARD_ID}-c"], "success")
        finally:
            db = get_db()
            cursor = db.cursor()
            try:
                for suffix in ("a", "b", "c"):
                    name = f"greenhouse:{TEST_BOARD_ID}-{suffix}"
                    cursor.execute(
                        "DELETE FROM jobs WHERE source_id IN (SELECT id FROM job_sources WHERE name=%s)",
                        (name,),
                    )
                    cursor.execute(
                        "DELETE FROM job_ingestion_runs WHERE source_id IN (SELECT id FROM job_sources WHERE name=%s)",
                        (name,),
                    )
                    cursor.execute("DELETE FROM job_sources WHERE name=%s", (name,))
                db.commit()
            finally:
                cursor.close()
                db.close()


if __name__ == "__main__":
    unittest.main()
