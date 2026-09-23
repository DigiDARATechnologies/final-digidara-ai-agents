import unittest
from unittest.mock import MagicMock, patch

from job_agent.providers.jsearch import (
    JSearchAPIError,
    JSearchNotConfigured,
    fetch_and_normalize,
    is_configured,
    normalize_job,
)
from job_agent.providers.config_loader import get_jsearch_config


class JSearchProviderTests(unittest.TestCase):
    def test_normalize_job_maps_jsearch_response_to_canonical_job(self):
        raw = {
            "job_id": "ab12cd34",
            "job_title": "React Developer Fresher",
            "employer_name": "Bangalore Tech Labs",
            "job_city": "Bengaluru",
            "job_state": "Karnataka",
            "job_country": "India",
            "job_is_remote": False,
            "job_employment_type": "FULLTIME",
            "job_apply_link": "https://www.linkedin.com/jobs/view/ab12cd34",
            "job_description": "Exciting opportunity for freshers proficient in React and JavaScript.",
            "job_required_skills": ["React", "JavaScript", "HTML"],
            "job_posted_at_datetime_utc": "2026-09-21T05:00:00.000Z",
            "job_min_salary": 400000,
            "job_max_salary": 600000,
            "job_salary_currency": "INR",
        }

        job = normalize_job(raw)
        self.assertIsNotNone(job)
        self.assertEqual(job["external_id"], "jsearch:ab12cd34")
        self.assertEqual(job["title"], "React Developer Fresher")
        self.assertEqual(job["company"], "Bangalore Tech Labs")
        self.assertEqual(job["location"], "Bengaluru, Karnataka, India")
        self.assertEqual(job["work_mode"], "onsite")
        self.assertEqual(job["apply_url"], "https://www.linkedin.com/jobs/view/ab12cd34")
        self.assertEqual(job["skills"], ["React", "JavaScript", "HTML"])
        self.assertEqual(job["source"], "jsearch")

    def test_normalize_job_rejects_missing_required_fields(self):
        self.assertIsNone(normalize_job({"job_id": "1", "job_title": "Dev"}))
        self.assertIsNone(normalize_job({"job_id": "1", "job_apply_link": "https://example.com"}))

    @patch("job_agent.providers.jsearch._token", return_value="test_token")
    def test_fetch_and_normalize_success(self, _token):
        session = MagicMock()
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "status": "OK",
            "data": [
                {
                    "job_id": "xyz789",
                    "job_title": "Python Engineer",
                    "employer_name": "Chennai AI Corp",
                    "job_city": "Chennai",
                    "job_apply_link": "https://example.com/job/xyz789",
                    "job_description": "Junior engineer position",
                }
            ]
        }
        session.get.return_value = response

        jobs = fetch_and_normalize("Python Fresher Chennai", session=session)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["external_id"], "jsearch:xyz789")
        self.assertEqual(jobs[0]["company"], "Chennai AI Corp")

    @patch.dict("os.environ", {}, clear=True)
    def test_fetch_raises_not_configured_when_missing_token(self):
        with self.assertRaises(JSearchNotConfigured):
            fetch_and_normalize("Software Engineer")

    @patch("job_agent.providers.jsearch._token", return_value="tok")
    def test_fetch_handles_unsubscribed_404_error(self, _token):
        session = MagicMock()
        session.get.return_value = MagicMock(status_code=404, text="Endpoint does not exist")
        with self.assertRaises(JSearchAPIError) as ctx:
            fetch_and_normalize("query", session=session)
        self.assertIn("inactive", str(ctx.exception).lower())

    def test_config_loader_reads_configured_jsearch_queries(self):
        config = get_jsearch_config({
            "jsearch": {
                "enabled": True,
                "queries": [
                    {"query": "Python Developer in Madurai"},
                ],
            }
        })
        self.assertTrue(config["enabled"])
        self.assertEqual(len(config["queries"]), 1)
        self.assertEqual(config["queries"][0]["query"], "Python Developer in Madurai")
