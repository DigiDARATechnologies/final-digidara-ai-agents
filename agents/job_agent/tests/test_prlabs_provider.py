import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from job_agent.free_plan import FREE_PLAN_LIMITS
from job_agent.providers.config_loader import get_prlabs_config
from job_agent.providers.prlabs import (
    PRLabsAPIError,
    PRLabsNotConfigured,
    fetch_and_normalize,
    is_configured,
    normalize_job,
)
from job_agent.providers.sync import _prlabs_source_name, queue_prlabs_collection, todays_slice, upcoming_plan
from job_agent.trust import evaluate_job_trust

# Shape of a real /getjobs reply (every value is a string).
RAW_JOB = {
    "id": "li-4310889000",
    "site": "linkedin",
    "job_url": "https://www.linkedin.com/jobs/view/4310889000",
    "job_url_direct": "",
    "title": "Senior Data Analyst",
    "company": "TEGNA",
    "location": "Chennai, Tamil Nadu, India",
    "date_posted": "2026-10-05",
    "job_type": "fulltime",
    "min_amount": "",
    "max_amount": "",
    "currency": "",
    "interval": "",
    "is_remote": "False",
    "description": "",
    "skills": "",
}


class PRLabsNormalizeTests(unittest.TestCase):
    def test_maps_a_linkedin_job_to_the_canonical_job(self):
        job = normalize_job(RAW_JOB)
        self.assertEqual(job["source"], "prlabs")
        self.assertEqual(job["external_id"], "prlabs:li-4310889000")
        self.assertEqual(job["title"], "Senior Data Analyst")
        self.assertEqual(job["company"], "TEGNA")
        self.assertEqual(job["location"], "Chennai, Tamil Nadu, India")
        self.assertEqual(job["work_mode"], "onsite")
        self.assertEqual(job["employment_type"], "Full Time")
        self.assertEqual(job["apply_url"], "https://www.linkedin.com/jobs/view/4310889000")
        self.assertTrue(job["published_at"].startswith("2026-10-05"))
        self.assertEqual(job["salary_text"], "")
        self.assertEqual(job["skills"], [])

    def test_prefers_the_direct_employer_link_and_reads_salary_and_remote(self):
        job = normalize_job({**RAW_JOB, "job_url_direct": "https://careers.example.com/1", "is_remote": "True",
                             "min_amount": "600000", "max_amount": "900000", "currency": "INR", "interval": "yearly",
                             "skills": "Python, SQL"})
        self.assertEqual(job["apply_url"], "https://careers.example.com/1")
        self.assertEqual(job["source_url"], "https://www.linkedin.com/jobs/view/4310889000")
        self.assertEqual(job["work_mode"], "remote")
        self.assertEqual(job["salary_text"], "INR 600,000 - INR 900,000 / yearly")
        self.assertEqual(job["skills"], ["Python", "SQL"])

    def test_rejects_jobs_without_id_title_or_a_web_link(self):
        self.assertIsNone(normalize_job({**RAW_JOB, "id": ""}))
        self.assertIsNone(normalize_job({**RAW_JOB, "title": ""}))
        self.assertIsNone(normalize_job({**RAW_JOB, "job_url": "javascript:alert(1)"}))
        self.assertIsNone(normalize_job("not a job"))


class PRLabsFetchTests(unittest.TestCase):
    def _session(self, status=200, body=None):
        session = MagicMock()
        response = MagicMock(status_code=status)
        response.json.return_value = body if body is not None else {"status": "True", "jobs": [RAW_JOB]}
        session.post.return_value = response
        return session

    @patch.dict(os.environ, {"PRLABS_API_KEY": "test-key"})
    def test_sends_the_key_as_a_header_and_counts_the_call_first(self):
        session, reserve = self._session(), MagicMock()
        jobs = fetch_and_normalize("Data Analyst", "Tamil Nadu, India", results_wanted=50, hours_old=72,
                                   session=session, before_request=reserve)
        self.assertEqual([job["external_id"] for job in jobs], ["prlabs:li-4310889000"])
        reserve.assert_called_once()
        url = session.post.call_args.args[0]
        kwargs = session.post.call_args.kwargs
        self.assertEqual(url, "https://api0.prlabsapi.com/getjobs")
        self.assertEqual(kwargs["headers"]["api_key"], "test-key")
        self.assertEqual(kwargs["json"]["search_term"], "Data Analyst")
        self.assertEqual(kwargs["json"]["location"], "Tamil Nadu, India")
        self.assertEqual(kwargs["json"]["site_name"], ["linkedin", "indeed"])
        self.assertEqual(kwargs["json"]["hours_old"], 72)  # the value passed in
        self.assertNotIn("test-key", str(kwargs["json"]))

    @patch.dict(os.environ, {"PRLABS_API_KEY": ""})
    def test_without_a_key_no_call_is_made(self):
        session, reserve = self._session(), MagicMock()
        self.assertFalse(is_configured())
        with self.assertRaises(PRLabsNotConfigured):
            fetch_and_normalize("Data Analyst", "Tamil Nadu, India", session=session, before_request=reserve)
        session.post.assert_not_called()
        reserve.assert_not_called()

    @patch.dict(os.environ, {"PRLABS_API_KEY": "test-key"})
    def test_errors_are_reported_without_the_key(self):
        for status in (401, 402, 429, 503, 418):
            with self.assertRaises(PRLabsAPIError) as caught:
                fetch_and_normalize("AI Engineer", "Tamil Nadu, India", session=self._session(status))
            self.assertNotIn("test-key", str(caught.exception))
        with self.assertRaises(PRLabsAPIError):
            fetch_and_normalize("AI Engineer", "Tamil Nadu, India",
                                session=self._session(body={"status": "False", "message": "no credits"}))


class PRLabsPlanTests(unittest.TestCase):
    def test_default_plan_searches_ai_data_and_web_roles_across_tamil_nadu(self):
        config = get_prlabs_config()
        self.assertTrue(config["enabled"])
        terms = {query["search_term"] for query in config["queries"]}
        self.assertTrue({"AI Engineer", "Data Analyst", "Data Scientist", "Web Developer", "Full Stack Developer"} <= terms)
        locations = {query["location"] for query in config["queries"]}
        self.assertIn("Tamil Nadu, India", locations)
        self.assertIn("Tiruchirappalli, Tamil Nadu, India", locations)
        self.assertEqual(config["sites"], ["linkedin", "indeed"])
        self.assertEqual(config["hours_old"], 168)

    def test_every_daily_block_searches_every_role_and_pairs_are_unique(self):
        config = get_prlabs_config({"prlabs": {"roles": ["A", "B", "C"], "locations": ["X", "Y"]}})
        queries = [(q["search_term"], q["location"]) for q in config["queries"]]
        self.assertEqual(len(set(queries)), 6)
        self.assertEqual({role for role, _ in queries[:3]}, {"A", "B", "C"})
        self.assertEqual({location for _, location in queries[:3]}, {"X", "Y"})

    def test_roles_and_locations_multiply_and_disabled_means_no_searches(self):
        config = get_prlabs_config({"prlabs": {"roles": ["AI Engineer", "Web Developer"], "locations": ["Chennai", "Coimbatore"]}})
        self.assertEqual(len(config["queries"]), 4)
        self.assertEqual(get_prlabs_config({"prlabs": {"enabled": False}})["enabled"], False)

    def test_source_names_are_stable_and_fit_the_column(self):
        self.assertEqual(_prlabs_source_name("AI Engineer", "Tamil Nadu, India"), "prlabs:ai_engineer:tamil_nadu_india")
        self.assertLessEqual(len(_prlabs_source_name("x" * 300, "y")), 150)

    def test_every_role_runs_within_the_daily_budget_rotation(self):
        searches = get_prlabs_config()["queries"]
        seen = set()
        for offset in range(3):
            day = date.fromordinal(date(2026, 10, 6).toordinal() + offset)
            seen.update(search["search_term"] for search in todays_slice(searches, 5, day))
        self.assertEqual(seen, {search["search_term"] for search in searches})

    def test_upcoming_plan_lists_prlabs_searches(self):
        plan = upcoming_plan(days=1, start=date(2026, 10, 6))
        self.assertTrue(plan[0]["prlabs"])
        self.assertEqual(len(plan[0]["prlabs"]), 14)
        self.assertTrue(all(entry.endswith("Tamil Nadu, India)") for entry in plan[0]["prlabs"]))

    def test_calls_are_capped_per_day_and_month(self):
        windows = {name for name, _, _ in FREE_PLAN_LIMITS["prlabs"]}
        self.assertEqual(windows, {"day", "month"})

    @patch.dict(os.environ, {"PRLABS_API_KEY": ""})
    def test_queue_is_skipped_until_the_key_is_set(self):
        result = queue_prlabs_collection()
        self.assertFalse(result["ready"])
        self.assertIn("PRLABS_API_KEY", result["reason"])


class PRLabsTrustTests(unittest.TestCase):
    def test_prlabs_jobs_are_labelled_aggregator_listings(self):
        trust = evaluate_job_trust({**normalize_job(RAW_JOB), "source_type": "prlabs",
                                    "description": "Build dashboards " * 30})
        self.assertEqual(trust["source_label"], "PR Labs Jobs API")
        self.assertEqual(trust["trust_level"], "aggregator")
        self.assertLessEqual(trust["trust_score"], 79)
        self.assertFalse(trust["is_verified"])

    def test_detected_from_external_id_when_source_type_is_missing(self):
        job = normalize_job({**RAW_JOB, "job_url_direct": "https://careers.example.com/jobs/1"})
        job.pop("source")
        trust = evaluate_job_trust(job)
        self.assertEqual(trust["source_label"], "PR Labs Jobs API")
        self.assertNotEqual(trust["trust_level"], "direct_employer")


if __name__ == "__main__":
    unittest.main()
