"""Source lifecycle tests: DISCOVERED / VALIDATING / ACTIVE /
TEMPORARILY_FAILED / INVALID / DISABLED.

Exercises the real database (this project has no DB-mocking harness; every
DB-backed test here follows the same convention as
test_greenhouse_integration.py) with the Greenhouse HTTP layer mocked.
Skipped, not failed, when MySQL is unreachable. Cleans up every row it
creates.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from job_agent.db import get_db, init_job_tables
from job_agent.providers.greenhouse import GreenhouseAPIError


TEST_BOARD_ID = "digidara-lifecycle-test-board"
TEST_COMPANY_NAME = "DigiDARA Lifecycle Test Co"
TEST_SOURCE_NAME = f"greenhouse:{TEST_BOARD_ID}"


def _mysql_available():
    try:
        db = get_db()
        db.close()
        return True
    except Exception:
        return False


def _sample_raw_job(job_id=901):
    return {
        "id": job_id,
        "title": "Lifecycle Test Engineer",
        "absolute_url": f"https://boards.greenhouse.io/{TEST_BOARD_ID}/jobs/{job_id}",
        "location": {"name": "Chennai, Tamil Nadu, India"},
        "departments": [{"name": "Engineering"}],
        "content": "Verify source lifecycle transitions.",
        "first_published": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-20T00:00:00Z",
    }


@unittest.skipUnless(_mysql_available(), "MySQL database is not reachable in this environment")
class SourceLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_job_tables()

    def setUp(self):
        self._cleanup_test_source()

    def tearDown(self):
        self._cleanup_test_source()

    def _cleanup_test_source(self):
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

    def _insert_source(self, status="discovered", is_active=1):
        db = get_db()
        cursor = db.cursor()
        try:
            source_url = f"https://boards-api.greenhouse.io/v1/boards/{TEST_BOARD_ID}/jobs?content=true"
            parser_config = json.dumps({"board_id": TEST_BOARD_ID, "company_name": TEST_COMPANY_NAME})
            cursor.execute(
                """INSERT INTO job_sources (name, source_type, source_url, parser_config, is_active,
                   scraping_authorized, status) VALUES (%s,'greenhouse',%s,%s,%s,1,%s)""",
                (TEST_SOURCE_NAME, source_url, parser_config, is_active, status),
            )
            db.commit()
            source_id = cursor.lastrowid
        finally:
            cursor.close()
            db.close()
        return source_id

    def _get_source(self, source_id):
        db = get_db()
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM job_sources WHERE id=%s", (source_id,))
            return cursor.fetchone()
        finally:
            cursor.close()
            db.close()

    def _run_source(self, source_id, admin_id=None):
        from job_agent.service import process_run, queue_source_run

        run_id = queue_source_run(source_id, admin_id)
        return process_run(run_id)

    # ---- status transitions from an actual process_run ----

    def test_successful_run_marks_source_active(self):
        source_id = self._insert_source(status="discovered")
        mock_session = MagicMock()
        mock_response = MagicMock(status_code=200, content=b"{}")
        mock_response.json.return_value = {"jobs": [_sample_raw_job()], "meta": {}}
        mock_session.get.return_value = mock_response

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            self._run_source(source_id)

        source = self._get_source(source_id)
        self.assertEqual(source["status"], "active")
        self.assertIsNone(source["error_category"])
        self.assertIsNone(source["last_error"])
        self.assertIsNotNone(source["last_success_at"])
        self.assertIsNotNone(source["last_attempted_at"])

    def test_successful_run_with_zero_raw_jobs_marks_source_empty_board(self):
        source_id = self._insert_source(status="discovered")
        mock_session = MagicMock()
        mock_response = MagicMock(status_code=200, content=b"{}")
        mock_response.json.return_value = {"jobs": [], "meta": {}}
        mock_session.get.return_value = mock_response

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            self._run_source(source_id)

        source = self._get_source(source_id)
        # A board that resolves but genuinely has zero published jobs is
        # not a failure - EMPTY_BOARD is its own status, distinct from
        # ACTIVE and from NO_MATCHING_JOBS (jobs exist but none passed
        # our filters).
        self.assertEqual(source["status"], "empty_board")
        self.assertEqual(source["last_fetched_count"], 0)
        self.assertIsNone(source["last_error"])
        self.assertIsNotNone(source["last_success_at"])

    def test_raw_jobs_all_filtered_out_marks_source_no_matching_jobs(self):
        source_id = self._insert_source(status="discovered")
        mock_session = MagicMock()
        mock_response = MagicMock(status_code=200, content=b"{}")
        # A real published job, but its location ("Berlin, Germany") does
        # not match any configured location keyword, so it never reaches
        # storage - this must read as "jobs exist but none matched", not
        # as a genuinely empty board.
        filtered_job = dict(_sample_raw_job(), location={"name": "Berlin, Germany"})
        mock_response.json.return_value = {"jobs": [filtered_job], "meta": {}}
        mock_session.get.return_value = mock_response

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            self._run_source(source_id)

        source = self._get_source(source_id)
        self.assertEqual(source["status"], "no_matching_jobs")
        self.assertEqual(source["last_fetched_count"], 1)
        self.assertIsNone(source["last_error"])

    def test_active_source_with_zero_tn_jobs_stays_active(self):
        source_id = self._insert_source(status="discovered")
        mock_session = MagicMock()
        mock_response = MagicMock(status_code=200, content=b"{}")
        # Matches the "bengaluru" location keyword (so it is kept), but
        # tn_location.py classifies Bengaluru as OTHER_INDIA, not
        # TAMIL_NADU - ACTIVE must not require tn_jobs > 0.
        bengaluru_job = dict(_sample_raw_job(), location={"name": "Bengaluru, Karnataka, India"})
        mock_response.json.return_value = {"jobs": [bengaluru_job], "meta": {}}
        mock_session.get.return_value = mock_response

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            self._run_source(source_id)

        source = self._get_source(source_id)
        self.assertEqual(source["status"], "active")
        self.assertEqual(source["last_fetched_count"], 1)

    def test_source_with_stored_jobs_stays_active_even_when_this_run_fetches_nothing(self):
        # Regression: a source with jobs already on file (from an earlier
        # run) must never flip to an empty/no-match status just because
        # THIS run's fetch came back empty - status reflects what is
        # actually stored, not only this run's transient outcome.
        source_id = self._insert_source(status="discovered")
        mock_session = MagicMock()
        first_response = MagicMock(status_code=200, content=b"{}")
        first_response.json.return_value = {"jobs": [_sample_raw_job()], "meta": {}}
        mock_session.get.return_value = first_response
        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            self._run_source(source_id)
        self.assertEqual(self._get_source(source_id)["status"], "active")

        second_response = MagicMock(status_code=200, content=b"{}")
        second_response.json.return_value = {"jobs": [], "meta": {}}
        mock_session.get.return_value = second_response
        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            self._run_source(source_id)

        source = self._get_source(source_id)
        self.assertEqual(source["status"], "active")
        self.assertEqual(source["last_fetched_count"], 0)

    def test_consecutive_failures_increments_on_repeated_failure_and_resets_on_success(self):
        source_id = self._insert_source(status="active")
        mock_session = MagicMock()
        mock_session.get.return_value = MagicMock(status_code=503, content=b"{}")

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            with self.assertRaises(GreenhouseAPIError):
                self._run_source(source_id)
        self.assertEqual(self._get_source(source_id)["consecutive_failures"], 1)

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            with self.assertRaises(GreenhouseAPIError):
                self._run_source(source_id)
        self.assertEqual(self._get_source(source_id)["consecutive_failures"], 2)

        mock_response = MagicMock(status_code=200, content=b"{}")
        mock_response.json.return_value = {"jobs": [_sample_raw_job()], "meta": {}}
        mock_session.get.return_value = mock_response
        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            self._run_source(source_id)
        self.assertEqual(self._get_source(source_id)["consecutive_failures"], 0)

    def test_last_validated_at_updates_on_every_attempt(self):
        source_id = self._insert_source(status="discovered")
        self.assertIsNone(self._get_source(source_id)["last_validated_at"])

        mock_session = MagicMock()
        mock_session.get.return_value = MagicMock(status_code=404, content=b"{}")
        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            with self.assertRaises(GreenhouseAPIError):
                self._run_source(source_id)

        self.assertIsNotNone(self._get_source(source_id)["last_validated_at"])

    def test_board_not_found_marks_source_invalid(self):
        source_id = self._insert_source(status="discovered")
        mock_session = MagicMock()
        mock_session.get.return_value = MagicMock(status_code=404, content=b"{}")

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            with self.assertRaises(GreenhouseAPIError):
                self._run_source(source_id)

        source = self._get_source(source_id)
        self.assertEqual(source["status"], "invalid")
        self.assertEqual(source["error_category"], "board_not_found")
        self.assertIsNotNone(source["last_attempted_at"])
        self.assertIsNone(source["last_success_at"])

    def test_timeout_marks_source_temporarily_failed_not_invalid(self):
        import requests

        source_id = self._insert_source(status="active")
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.Timeout("timed out")

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            with self.assertRaises(GreenhouseAPIError):
                self._run_source(source_id)

        source = self._get_source(source_id)
        # Transient failure: eligible for automatic retry next run, unlike
        # a permanent board_not_found which is marked INVALID instead.
        self.assertEqual(source["status"], "temporarily_failed")
        self.assertEqual(source["error_category"], "timeout")

    def test_server_error_marks_source_temporarily_failed(self):
        source_id = self._insert_source(status="active")
        mock_session = MagicMock()
        mock_session.get.return_value = MagicMock(status_code=503, content=b"{}")

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            with self.assertRaises(GreenhouseAPIError):
                self._run_source(source_id)

        source = self._get_source(source_id)
        self.assertEqual(source["status"], "temporarily_failed")
        self.assertEqual(source["error_category"], "server_error")

    def test_successful_retry_after_temporary_failure_returns_to_active(self):
        source_id = self._insert_source(status="temporarily_failed")
        mock_session = MagicMock()
        mock_response = MagicMock(status_code=200, content=b"{}")
        mock_response.json.return_value = {"jobs": [_sample_raw_job()], "meta": {}}
        mock_session.get.return_value = mock_response

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            self._run_source(source_id)

        source = self._get_source(source_id)
        self.assertEqual(source["status"], "active")
        self.assertIsNone(source["last_error"])

    # ---- automatic-run source selection excludes INVALID ----

    def test_invalid_source_excluded_from_automatic_selection(self):
        from job_agent.providers.sync import _active_greenhouse_sources

        self._insert_source(status="invalid")
        names = {s["name"] for s in _active_greenhouse_sources()}
        self.assertNotIn(TEST_SOURCE_NAME, names)

    def test_temporarily_failed_source_still_included_in_automatic_selection(self):
        from job_agent.providers.sync import _active_greenhouse_sources

        self._insert_source(status="temporarily_failed")
        names = {s["name"] for s in _active_greenhouse_sources()}
        self.assertIn(TEST_SOURCE_NAME, names)

    def test_disabled_source_excluded_from_automatic_selection(self):
        from job_agent.providers.sync import _active_greenhouse_sources

        self._insert_source(status="disabled", is_active=0)
        names = {s["name"] for s in _active_greenhouse_sources()}
        self.assertNotIn(TEST_SOURCE_NAME, names)

    def test_discovered_source_included_in_automatic_selection(self):
        from job_agent.providers.sync import _active_greenhouse_sources

        self._insert_source(status="discovered")
        names = {s["name"] for s in _active_greenhouse_sources()}
        self.assertIn(TEST_SOURCE_NAME, names)

    # ---- explicit revalidation (GOAL 3's "allow it to be revalidated later") ----

    def test_revalidate_forces_reattempt_of_invalid_source(self):
        from job_agent.providers.sync import revalidate_greenhouse_source

        source_id = self._insert_source(status="invalid")
        mock_session = MagicMock()
        mock_response = MagicMock(status_code=200, content=b"{}")
        mock_response.json.return_value = {"jobs": [_sample_raw_job()], "meta": {}}
        mock_session.get.return_value = mock_response

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            outcome = revalidate_greenhouse_source(source_id)

        self.assertEqual(outcome["run"]["status"], "success")
        self.assertEqual(outcome["source"]["status"], "active")

    def test_revalidate_of_still_broken_source_reports_failure_without_raising(self):
        from job_agent.providers.sync import revalidate_greenhouse_source

        source_id = self._insert_source(status="invalid")
        mock_session = MagicMock()
        mock_session.get.return_value = MagicMock(status_code=404, content=b"{}")

        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            outcome = revalidate_greenhouse_source(source_id)

        self.assertEqual(outcome["run"]["status"], "failed")
        self.assertEqual(outcome["source"]["status"], "invalid")

    def test_revalidate_unknown_source_returns_none(self):
        from job_agent.providers.sync import revalidate_greenhouse_source

        self.assertIsNone(revalidate_greenhouse_source(2**31 - 1))

    # ---- sync must not clobber existing health status ----

    def _real_companies_config(self, include_test_board):
        """Build a providers.yaml-shaped config from the REAL configured companies.

        sync_greenhouse_sources() disables every job_sources row whose name
        isn't in the mocked config's company list - it operates on the
        whole shared `job_sources` table, not just rows a test created.
        Mocking a config with only the synthetic test company (or an empty
        one) would therefore disable every real Greenhouse company's row
        in the database as a side effect. Including the real, currently
        configured companies here (read live, not hardcoded) keeps every
        sync-related test scoped to only the row it created.
        """
        from job_agent.providers.config_loader import get_greenhouse_companies

        companies = [dict(company, enabled=True) for company in get_greenhouse_companies()]
        if include_test_board:
            companies.append({"name": TEST_COMPANY_NAME, "board_id": TEST_BOARD_ID, "enabled": True})
        return {"greenhouse": {"enabled": True, "companies": companies}}

    def test_sync_does_not_reset_invalid_status_back_to_healthy(self):
        from job_agent.providers.sync import sync_greenhouse_sources

        source_id = self._insert_source(status="invalid")
        config = self._real_companies_config(include_test_board=True)
        with patch("job_agent.providers.config_loader.load_providers_config", return_value=config):
            sync_greenhouse_sources()

        source = self._get_source(source_id)
        self.assertEqual(source["status"], "invalid")
        self.assertEqual(source["is_active"], 1)

    def test_sync_marks_company_removed_from_config_as_disabled(self):
        from job_agent.providers.sync import sync_greenhouse_sources

        source_id = self._insert_source(status="active")
        # Real companies stay in the config; only the synthetic test board
        # is left out, simulating it being removed from providers.yaml.
        config = self._real_companies_config(include_test_board=False)
        with patch("job_agent.providers.config_loader.load_providers_config", return_value=config):
            sync_greenhouse_sources()

        source = self._get_source(source_id)
        self.assertEqual(source["status"], "disabled")
        self.assertEqual(source["is_active"], 0)

    def test_sync_reactivates_a_previously_disabled_company_that_returns_to_config(self):
        from job_agent.providers.sync import sync_greenhouse_sources

        source_id = self._insert_source(status="disabled", is_active=0)
        config = self._real_companies_config(include_test_board=True)
        with patch("job_agent.providers.config_loader.load_providers_config", return_value=config):
            sync_greenhouse_sources()

        source = self._get_source(source_id)
        self.assertEqual(source["is_active"], 1)
        self.assertNotEqual(source["status"], "disabled")

    def test_sync_is_idempotent_for_a_healthy_source(self):
        from job_agent.providers.sync import sync_greenhouse_sources

        source_id = self._insert_source(status="active")
        config = self._real_companies_config(include_test_board=True)
        with patch("job_agent.providers.config_loader.load_providers_config", return_value=config):
            sync_greenhouse_sources()
            sync_greenhouse_sources()

        source = self._get_source(source_id)
        self.assertEqual(source["status"], "active")
        self.assertEqual(source["is_active"], 1)


if __name__ == "__main__":
    unittest.main()
