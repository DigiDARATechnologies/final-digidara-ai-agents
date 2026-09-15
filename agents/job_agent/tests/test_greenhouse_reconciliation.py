"""Milestone 1.1 regression tests: aggregate job-count reconciliation and
source status semantics (EMPTY_BOARD / NO_MATCHING_JOBS / ACTIVE).

Exercises the real database (this project has no DB-mocking harness),
skipped rather than failed when MySQL is unreachable. `get_greenhouse_companies`
is patched to a synthetic single-company list so these tests are fully
self-contained and never touch or depend on the real providers.yaml
registry.
"""

import hashlib
import json
import unittest
from unittest.mock import MagicMock, patch

from job_agent.db import get_db, init_job_tables


TEST_BOARD_ID = "digidara-reconciliation-test-board"
TEST_COMPANY_NAME = "DigiDARA Reconciliation Test Co"
TEST_SOURCE_NAME = f"greenhouse:{TEST_BOARD_ID}"


def _mysql_available():
    try:
        db = get_db()
        db.close()
        return True
    except Exception:
        return False


def _test_company():
    return {
        "name": TEST_COMPANY_NAME, "board_id": TEST_BOARD_ID,
        "district": None, "city": None, "state": None, "country": None, "category": None,
    }


@unittest.skipUnless(_mysql_available(), "MySQL database is not reachable in this environment")
class GreenhouseReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_job_tables()

    def setUp(self):
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
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

    def _insert_source(self, status="active"):
        db = get_db()
        cursor = db.cursor()
        try:
            source_url = f"https://boards-api.greenhouse.io/v1/boards/{TEST_BOARD_ID}/jobs?content=true"
            parser_config = json.dumps({"board_id": TEST_BOARD_ID, "company_name": TEST_COMPANY_NAME})
            cursor.execute(
                """INSERT INTO job_sources (name, source_type, source_url, parser_config, is_active,
                   scraping_authorized, status) VALUES (%s,'greenhouse',%s,%s,1,1,%s)""",
                (TEST_SOURCE_NAME, source_url, parser_config, status),
            )
            db.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            db.close()

    def _insert_job(self, source_id, external_id, location_region):
        db = get_db()
        cursor = db.cursor()
        try:
            content_hash = hashlib.sha256(f"{external_id}|{source_id}".encode()).hexdigest()
            cursor.execute(
                """INSERT INTO jobs (source_id, external_id, title, company, location,
                   location_region, apply_url, content_hash, status)
                   VALUES (%s,%s,'Test Engineer',%s,'Test Location',%s,%s,%s,'pending')""",
                (
                    source_id, external_id, TEST_COMPANY_NAME, location_region,
                    f"https://example.test/{external_id}", content_hash,
                ),
            )
            db.commit()
        finally:
            cursor.close()
            db.close()

    def _get_source(self, source_id):
        db = get_db()
        cursor = db.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM job_sources WHERE id=%s", (source_id,))
            return cursor.fetchone()
        finally:
            cursor.close()
            db.close()

    def _run_source(self, source_id):
        from job_agent.service import process_run, queue_source_run

        run_id = queue_source_run(source_id, None)
        return process_run(run_id)

    # ---- aggregate reconciliation ----

    def test_company_row_region_breakdown_sums_to_total_and_survives_location_filtering(self):
        """10 fetched: 3 TN, 5 Other India, 1 International, 1 Unknown -> ACTIVE, total=10."""
        from job_agent.routes import _greenhouse_company_rows

        source_id = self._insert_source()
        for i in range(3):
            self._insert_job(source_id, f"tn-{i}", "TAMIL_NADU")
        for i in range(5):
            self._insert_job(source_id, f"oi-{i}", "OTHER_INDIA")
        self._insert_job(source_id, "intl-0", "INTERNATIONAL")
        self._insert_job(source_id, "unk-0", None)

        with patch("job_agent.routes.get_greenhouse_companies", return_value=[_test_company()]):
            rows = _greenhouse_company_rows()

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["total_jobs"], 10)
        self.assertEqual(row["tn_job_count"], 3)
        self.assertEqual(row["other_india_job_count"], 5)
        self.assertEqual(row["international_job_count"], 1)
        self.assertEqual(row["unknown_location_job_count"], 1)
        self.assertEqual(
            row["tn_job_count"] + row["other_india_job_count"]
            + row["international_job_count"] + row["unknown_location_job_count"],
            row["total_jobs"],
        )
        self.assertEqual(row["status"], "active")

    def test_multi_company_aggregate_equals_sum_of_company_totals(self):
        """sum(company.total_jobs) across the registry must equal the aggregate total exactly."""
        from job_agent.routes import _greenhouse_company_rows

        source_id = self._insert_source()
        self._insert_job(source_id, "a", "TAMIL_NADU")
        self._insert_job(source_id, "b", "TAMIL_NADU")
        self._insert_job(source_id, "c", "OTHER_INDIA")

        second_board_id = TEST_BOARD_ID + "-2"
        second_name = f"greenhouse:{second_board_id}"
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                """INSERT INTO job_sources (name, source_type, source_url, parser_config, is_active,
                   scraping_authorized, status) VALUES (%s,'greenhouse','https://example.test','{}',1,1,'active')""",
                (second_name,),
            )
            db.commit()
            second_source_id = cursor.lastrowid
        finally:
            cursor.close()
            db.close()
        self._insert_job(second_source_id, "d", "OTHER_INDIA")

        companies = [_test_company(), {**_test_company(), "name": "Second Co", "board_id": second_board_id}]
        try:
            with patch("job_agent.routes.get_greenhouse_companies", return_value=companies):
                rows = _greenhouse_company_rows()

            overall_total = sum(row["total_jobs"] for row in rows)
            overall_tn = sum(row["tn_job_count"] for row in rows)
            overall_other_india = sum(row["other_india_job_count"] for row in rows)
            self.assertEqual(overall_total, 4)
            self.assertEqual(overall_tn, 2)
            self.assertEqual(overall_other_india, 2)
            self.assertEqual(overall_tn + overall_other_india, overall_total)
        finally:
            db = get_db()
            cursor = db.cursor()
            try:
                cursor.execute("DELETE FROM jobs WHERE source_id=%s", (second_source_id,))
                cursor.execute("DELETE FROM job_sources WHERE id=%s", (second_source_id,))
                db.commit()
            finally:
                cursor.close()
                db.close()

    # ---- status semantics ----

    def test_empty_board_has_zero_total_jobs(self):
        from job_agent.routes import _greenhouse_company_rows

        source_id = self._insert_source(status="discovered")
        mock_session = MagicMock()
        mock_response = MagicMock(status_code=200, content=b"{}")
        mock_response.json.return_value = {"jobs": [], "meta": {}}
        mock_session.get.return_value = mock_response
        with patch("job_agent.providers.greenhouse.requests.Session", return_value=mock_session):
            self._run_source(source_id)

        with patch("job_agent.routes.get_greenhouse_companies", return_value=[_test_company()]):
            rows = _greenhouse_company_rows()
        row = rows[0]
        self.assertEqual(row["status"], "empty_board")
        self.assertEqual(row["total_jobs"], 0)

    def test_sony_music_regression_stored_job_never_reports_empty(self):
        """A source with total_jobs=1 must never carry status=empty_board (or the old 'empty')."""
        source_id = self._insert_source(status="active")
        self._insert_job(source_id, "sony-1", "TAMIL_NADU")

        from job_agent.routes import _greenhouse_company_rows
        with patch("job_agent.routes.get_greenhouse_companies", return_value=[_test_company()]):
            rows = _greenhouse_company_rows()
        row = rows[0]
        self.assertEqual(row["total_jobs"], 1)
        self.assertEqual(row["tn_job_count"], 1)
        self.assertNotEqual(row["status"], "empty_board")
        self.assertNotEqual(row["status"], "empty")


if __name__ == "__main__":
    unittest.main()
