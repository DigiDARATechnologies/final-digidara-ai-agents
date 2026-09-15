import json
import unittest
from unittest.mock import MagicMock

import requests

from job_agent.providers.greenhouse import (
    GreenhouseAPIError,
    _is_entry_level,
    _location_matches,
    _validate_board_id,
    fetch_and_normalize,
    fetch_company_jobs,
    normalize_job,
)


def _mock_response(status_code=200, json_data=None, json_error=False, content=b"{}"):
    response = MagicMock()
    response.status_code = status_code
    response.content = content
    if json_error:
        response.json.side_effect = ValueError("invalid json")
    else:
        response.json.return_value = json_data
    return response


def _sample_job(job_id=101, title="Backend Engineer"):
    return {
        "id": job_id,
        "title": title,
        "absolute_url": f"https://boards.greenhouse.io/sagentindia/jobs/{job_id}",
        "location": {"name": "Chennai, Tamil Nadu, India"},
        "departments": [{"name": "Engineering"}],
        "offices": [{"name": "Chennai"}],
        "metadata": [{"name": "Employment Type", "value": "Full-time"}],
        "content": "<p>Build and ship <b>backend</b> services.</p>",
        "first_published": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-20T00:00:00Z",
    }


class FetchCompanyJobsTests(unittest.TestCase):
    def test_successful_company_job_retrieval(self):
        session = MagicMock()
        session.get.return_value = _mock_response(200, {"jobs": [_sample_job(1), _sample_job(2)], "meta": {}})
        jobs = fetch_company_jobs("sagentindia", session=session)
        self.assertEqual(len(jobs), 2)
        session.get.assert_called_once()
        called_url = session.get.call_args[0][0]
        self.assertIn("boards-api.greenhouse.io/v1/boards/sagentindia/jobs", called_url)

    def test_multiple_companies_are_independent(self):
        session_a = MagicMock()
        session_a.get.return_value = _mock_response(200, {"jobs": [_sample_job(1)]})
        session_b = MagicMock()
        session_b.get.return_value = _mock_response(200, {"jobs": [_sample_job(2), _sample_job(3)]})

        jobs_a = fetch_company_jobs("sagentindia", session=session_a)
        jobs_b = fetch_company_jobs("appian", session=session_b)
        self.assertEqual(len(jobs_a), 1)
        self.assertEqual(len(jobs_b), 2)

    def test_empty_board_returns_no_jobs(self):
        session = MagicMock()
        session.get.return_value = _mock_response(200, {"jobs": []})
        self.assertEqual(fetch_company_jobs("emptyboard", session=session), [])

    def test_http_404_raises_greenhouse_error(self):
        session = MagicMock()
        session.get.return_value = _mock_response(404, {})
        with self.assertRaises(GreenhouseAPIError) as ctx:
            fetch_company_jobs("unknownboard", session=session)
        self.assertEqual(ctx.exception.status_code, 404)
        # board_not_found is permanent: retrying on the next scheduled run
        # is pointless until the board id is fixed, so the source lifecycle
        # (service.process_run) marks it INVALID rather than
        # TEMPORARILY_FAILED, excluding it from automatic re-attempts.
        self.assertEqual(ctx.exception.category, "board_not_found")
        self.assertTrue(ctx.exception.permanent)

    def test_http_403_raises_greenhouse_error_as_transient_not_permanent(self):
        session = MagicMock()
        session.get.return_value = _mock_response(403, {})
        with self.assertRaises(GreenhouseAPIError) as ctx:
            fetch_company_jobs("sagentindia", session=session)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.category, "forbidden")
        # Unlike 404 (board genuinely gone), 403 may be a temporary
        # bot/WAF block on an otherwise-real board - retried, not INVALID.
        self.assertFalse(ctx.exception.permanent)

    def test_http_429_raises_greenhouse_error(self):
        session = MagicMock()
        session.get.return_value = _mock_response(429, {})
        with self.assertRaises(GreenhouseAPIError) as ctx:
            fetch_company_jobs("sagentindia", session=session)
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(ctx.exception.category, "rate_limited")
        self.assertFalse(ctx.exception.permanent)

    def test_http_500_raises_greenhouse_error(self):
        session = MagicMock()
        session.get.return_value = _mock_response(500, {})
        with self.assertRaises(GreenhouseAPIError) as ctx:
            fetch_company_jobs("sagentindia", session=session)
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(ctx.exception.category, "server_error")
        self.assertFalse(ctx.exception.permanent)

    def test_unexpected_status_code_is_treated_as_transient(self):
        session = MagicMock()
        session.get.return_value = _mock_response(302, {})
        with self.assertRaises(GreenhouseAPIError) as ctx:
            fetch_company_jobs("sagentindia", session=session)
        self.assertEqual(ctx.exception.category, "unexpected_response")
        self.assertFalse(ctx.exception.permanent)

    def test_timeout_raises_greenhouse_error(self):
        session = MagicMock()
        session.get.side_effect = requests.Timeout("timed out")
        with self.assertRaises(GreenhouseAPIError) as ctx:
            fetch_company_jobs("sagentindia", session=session)
        self.assertEqual(ctx.exception.category, "timeout")
        self.assertFalse(ctx.exception.permanent)

    def test_connection_error_raises_greenhouse_error(self):
        session = MagicMock()
        session.get.side_effect = requests.ConnectionError("no route to host")
        with self.assertRaises(GreenhouseAPIError) as ctx:
            fetch_company_jobs("sagentindia", session=session)
        self.assertEqual(ctx.exception.category, "network_error")
        self.assertFalse(ctx.exception.permanent)

    def test_malformed_json_raises_greenhouse_error(self):
        session = MagicMock()
        session.get.return_value = _mock_response(200, json_error=True)
        with self.assertRaises(GreenhouseAPIError) as ctx:
            fetch_company_jobs("sagentindia", session=session)
        self.assertEqual(ctx.exception.category, "malformed_response")
        self.assertFalse(ctx.exception.permanent)

    def test_non_mapping_response_raises_greenhouse_error(self):
        session = MagicMock()
        session.get.return_value = _mock_response(200, ["not", "a", "dict"])
        with self.assertRaises(GreenhouseAPIError) as ctx:
            fetch_company_jobs("sagentindia", session=session)
        self.assertEqual(ctx.exception.category, "unexpected_response")

    def test_large_response_falls_back_to_metadata_only_request(self):
        # A board whose full-description payload exceeds the configured
        # limit should not fail outright: fetch_company_jobs retries once
        # without content=true (a much smaller, metadata-only payload)
        # rather than raising, or requiring every other company's limit to
        # be raised. Descriptions come back empty for this board only.
        session = MagicMock()
        oversized = MagicMock()
        oversized.status_code = 200
        oversized.content = b"x" * (20 * 1024 * 1024)  # bigger than GREENHOUSE_MAX_RESPONSE_BYTES
        fallback = _mock_response(200, {"jobs": [_sample_job(1)], "meta": {}})
        session.get.side_effect = [oversized, fallback]

        jobs = fetch_company_jobs("bigboard", session=session)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(session.get.call_count, 2)
        first_url = session.get.call_args_list[0][0][0]
        second_url = session.get.call_args_list[1][0][0]
        self.assertIn("content=true", first_url)
        self.assertNotIn("content=true", second_url)

    def test_response_still_too_large_without_content_raises(self):
        # If even the metadata-only fallback exceeds the limit, this is a
        # genuinely oversized board and should raise (transient, so it
        # will be retried on the next scheduled run) rather than loop
        # forever or silently return nothing.
        session = MagicMock()
        oversized = MagicMock()
        oversized.status_code = 200
        oversized.content = b"x" * (20 * 1024 * 1024)
        session.get.side_effect = [oversized, oversized]

        with self.assertRaises(GreenhouseAPIError) as ctx:
            fetch_company_jobs("hugeboard", session=session)
        self.assertEqual(ctx.exception.category, "response_size_limit")
        self.assertEqual(session.get.call_count, 2)

    def test_pagination_follows_next_page(self):
        session = MagicMock()
        page1 = _mock_response(200, {"jobs": [_sample_job(1)], "meta": {"next_page": "https://boards-api.greenhouse.io/v1/boards/sagentindia/jobs?page=2"}})
        page2 = _mock_response(200, {"jobs": [_sample_job(2)], "meta": {}})
        session.get.side_effect = [page1, page2]
        jobs = fetch_company_jobs("sagentindia", session=session)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(session.get.call_count, 2)

    def test_invalid_board_id_is_rejected(self):
        with self.assertRaises(GreenhouseAPIError) as ctx:
            _validate_board_id("../../etc/passwd")
        self.assertEqual(ctx.exception.category, "invalid_configuration")
        self.assertTrue(ctx.exception.permanent)
        with self.assertRaises(GreenhouseAPIError):
            _validate_board_id("")


class NormalizeJobTests(unittest.TestCase):
    def test_maps_greenhouse_fields_to_canonical_job(self):
        raw = _sample_job(101, "Backend Engineer")
        job = normalize_job(raw, "Sagent India", "sagentindia")
        self.assertIsNotNone(job)
        self.assertEqual(job["source"], "greenhouse")
        self.assertEqual(job["source_job_id"], "101")
        self.assertEqual(job["external_id"], "101")
        self.assertEqual(job["company"], "Sagent India")
        self.assertEqual(job["title"], "Backend Engineer")
        self.assertIn("Build and ship backend services", job["description"])
        self.assertIn("Chennai", job["location"])
        self.assertEqual(job["department"], "Engineering")
        self.assertEqual(job["employment_type"], "Full-time")
        self.assertEqual(job["job_url"], raw["absolute_url"])
        self.assertEqual(job["application_url"], raw["absolute_url"])
        self.assertEqual(job["apply_url"], raw["absolute_url"])
        self.assertEqual(job["posted_at"], "2026-08-01 00:00:00")
        self.assertEqual(job["updated_at"], "2026-08-20 00:00:00")

    def test_remote_location_maps_to_remote_work_mode(self):
        raw = _sample_job(102)
        raw["location"] = {"name": "Remote - India"}
        job = normalize_job(raw, "Sagent India", "sagentindia")
        self.assertEqual(job["workplace_type"], "remote")
        self.assertEqual(job["work_mode"], "remote")

    def test_missing_required_fields_return_none(self):
        self.assertIsNone(normalize_job({"id": 1, "title": ""}, "Sagent India", "sagentindia"))
        self.assertIsNone(normalize_job({"id": "", "title": "Engineer", "absolute_url": "https://x"}, "Sagent India", "sagentindia"))
        self.assertIsNone(normalize_job({"id": 1, "title": "Engineer"}, "Sagent India", "sagentindia"))

    def test_does_not_invent_employment_type_when_absent(self):
        raw = _sample_job(103)
        raw["metadata"] = []
        job = normalize_job(raw, "Sagent India", "sagentindia")
        self.assertEqual(job["employment_type"], "")

    def test_department_empty_when_no_departments_listed(self):
        raw = _sample_job(104)
        raw["departments"] = []
        job = normalize_job(raw, "Sagent India", "sagentindia")
        self.assertEqual(job["department"], "")


class FetchAndNormalizeTests(unittest.TestCase):
    def test_end_to_end_fetch_and_normalize_skips_invalid_entries(self):
        session = MagicMock()
        valid_job = _sample_job(201, "QA Engineer")
        invalid_job = {"id": None, "title": "Missing id"}
        session.get.return_value = _mock_response(200, {"jobs": [valid_job, invalid_job]})

        jobs = fetch_and_normalize("sagentindia", "Sagent India", session=session)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["title"], "QA Engineer")

    def test_jobs_outside_target_locations_are_dropped(self):
        session = MagicMock()
        chennai_job = _sample_job(301, "Software Engineer")
        chennai_job["location"] = {"name": "Chennai, Tamil Nadu, India"}
        mumbai_job = _sample_job(302, "Software Engineer")
        mumbai_job["location"] = {"name": "Mumbai, Maharashtra, India"}
        session.get.return_value = _mock_response(200, {"jobs": [chennai_job, mumbai_job]})

        jobs = fetch_and_normalize("sagentindia", "Sagent India", session=session)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["location"], "Chennai, Tamil Nadu, India")

    def test_raw_count_reflects_pre_filter_total_not_the_filtered_result(self):
        session = MagicMock()
        chennai_job = _sample_job(301, "Software Engineer")
        chennai_job["location"] = {"name": "Chennai, Tamil Nadu, India"}
        mumbai_job = _sample_job(302, "Software Engineer")
        mumbai_job["location"] = {"name": "Mumbai, Maharashtra, India"}
        session.get.return_value = _mock_response(200, {"jobs": [chennai_job, mumbai_job]})

        jobs = fetch_and_normalize("sagentindia", "Sagent India", session=session)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs.raw_count, 2)

    def test_raw_count_is_zero_for_a_genuinely_empty_board(self):
        session = MagicMock()
        session.get.return_value = _mock_response(200, {"jobs": []})

        jobs = fetch_and_normalize("sagentindia", "Sagent India", session=session)
        self.assertEqual(len(jobs), 0)
        self.assertEqual(jobs.raw_count, 0)

    def test_senior_titles_are_dropped_by_default(self):
        session = MagicMock()
        entry_job = _sample_job(401, "Software Engineer")
        senior_job = _sample_job(402, "Senior Software Engineer")
        manager_job = _sample_job(403, "Engineering Manager")
        session.get.return_value = _mock_response(200, {"jobs": [entry_job, senior_job, manager_job]})

        jobs = fetch_and_normalize("sagentindia", "Sagent India", session=session)
        titles = {job["title"] for job in jobs}
        self.assertEqual(titles, {"Software Engineer"})

    def test_entry_keyword_overrides_exclude_keyword(self):
        session = MagicMock()
        job = _sample_job(501, "Associate Lead Program (Graduate Track)")
        session.get.return_value = _mock_response(200, {"jobs": [job]})

        jobs = fetch_and_normalize("sagentindia", "Sagent India", session=session)
        self.assertEqual(len(jobs), 1)

    def test_custom_filters_parameter_is_honoured(self):
        session = MagicMock()
        job = _sample_job(601, "Senior Software Engineer")
        job["location"] = {"name": "Remote - Anywhere"}
        session.get.return_value = _mock_response(200, {"jobs": [job]})

        permissive_filters = {
            "entry_level_only": False,
            "location_keywords": [],
            "exclude_title_keywords": [],
            "entry_title_keywords": [],
        }
        jobs = fetch_and_normalize("sagentindia", "Sagent India", session=session, filters=permissive_filters)
        self.assertEqual(len(jobs), 1)


class LocationAndSeniorityHelperTests(unittest.TestCase):
    def test_location_matches_target_cities_and_state(self):
        keywords = ["chennai", "bengaluru", "hyderabad", "tamil nadu"]
        self.assertTrue(_location_matches("Chennai, Tamil Nadu", keywords))
        self.assertTrue(_location_matches("Bengaluru, Karnataka", keywords))
        self.assertTrue(_location_matches("Hyderabad, Telangana", keywords))
        self.assertFalse(_location_matches("Mumbai, Maharashtra", keywords))
        self.assertFalse(_location_matches("", keywords))

    def test_location_matches_everything_when_no_keywords_configured(self):
        self.assertTrue(_location_matches("Anywhere on Earth", []))

    def test_is_entry_level_excludes_senior_titles(self):
        exclude = ["senior", "lead", "manager"]
        entry = ["junior", "associate", "graduate"]
        self.assertFalse(_is_entry_level("Senior Backend Engineer", exclude, entry))
        self.assertFalse(_is_entry_level("Engineering Manager", exclude, entry))
        self.assertTrue(_is_entry_level("Backend Engineer", exclude, entry))
        self.assertTrue(_is_entry_level("Junior Backend Engineer", exclude, entry))

    def test_entry_keyword_wins_over_exclude_keyword(self):
        exclude = ["lead"]
        entry = ["associate"]
        self.assertTrue(_is_entry_level("Associate Team Lead Program", exclude, entry))


if __name__ == "__main__":
    unittest.main()
