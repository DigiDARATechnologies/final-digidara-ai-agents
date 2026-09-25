import unittest
from unittest.mock import MagicMock, patch

from job_agent.providers.adzuna import (
    AdzunaAPIError,
    AdzunaNotConfigured,
    fetch_and_normalize,
    is_configured,
    normalize_job,
)
from job_agent.providers.config_loader import get_adzuna_config


class AdzunaProviderTests(unittest.TestCase):
    def test_normalize_job_maps_adzuna_response_to_canonical_job(self):
        raw = {
            "id": "5870528039",
            "title": "Software Engineer Fresher",
            "company": {"display_name": "Tech Corp Chennai"},
            "location": {"display_name": "Chennai, Tamil Nadu"},
            "description": "We are hiring junior Python developers with SQL knowledge.",
            "redirect_url": "https://www.adzuna.in/land/ad/5870528039",
            "created": "2026-09-20T10:00:00Z",
            "salary_min": 350000,
            "salary_max": 500000,
            "contract_time": "full_time",
        }

        job = normalize_job(raw)
        self.assertIsNotNone(job)
        self.assertEqual(job["external_id"], "adzuna:5870528039")
        self.assertEqual(job["title"], "Software Engineer Fresher")
        self.assertEqual(job["company"], "Tech Corp Chennai")
        self.assertEqual(job["location"], "Chennai, Tamil Nadu")
        self.assertEqual(job["apply_url"], "https://www.adzuna.in/land/ad/5870528039")
        self.assertEqual(job["source"], "adzuna")
        self.assertIn("\u20b9350,000", job["salary_text"])
        self.assertEqual(job["work_mode"], "onsite")

    def test_normalize_job_rejects_missing_required_fields(self):
        self.assertIsNone(normalize_job({"id": "1", "title": "Dev"}))
        self.assertIsNone(normalize_job({"id": "1", "redirect_url": "https://example.com"}))
        self.assertIsNone(normalize_job({"title": "Dev", "redirect_url": "https://example.com"}))

    def test_work_mode_detection(self):
        remote_job = normalize_job({
            "id": "2",
            "title": "Remote Python Developer",
            "redirect_url": "https://example.com/2",
            "description": "This is a full remote role.",
        })
        self.assertEqual(remote_job["work_mode"], "remote")

    @patch("job_agent.providers.adzuna._credentials", return_value=("test_app_id", "test_app_key"))
    def test_fetch_and_normalize_success(self, _creds):
        session = MagicMock()
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "results": [
                {
                    "id": "101",
                    "title": "Junior Web Developer",
                    "company": {"display_name": "Madurai Tech"},
                    "location": {"display_name": "Madurai, Tamil Nadu"},
                    "redirect_url": "https://example.com/job/101",
                    "description": "Looking for entry level web developer.",
                }
            ]
        }
        session.get.return_value = response

        jobs = fetch_and_normalize("Developer", "Madurai", session=session)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["external_id"], "adzuna:101")
        self.assertEqual(jobs[0]["company"], "Madurai Tech")

    @patch.dict("os.environ", {}, clear=True)
    def test_fetch_raises_not_configured_when_missing_credentials(self):
        with self.assertRaises(AdzunaNotConfigured):
            fetch_and_normalize("Developer", "Chennai")

    @patch("job_agent.providers.adzuna._credentials", return_value=("id", "key"))
    def test_fetch_handles_api_http_error(self, _creds):
        session = MagicMock()
        session.get.return_value = MagicMock(status_code=500, text="Internal Server Error")
        with self.assertRaises(AdzunaAPIError):
            fetch_and_normalize("Developer", "Chennai", session=session)

    def test_config_loader_reads_configured_adzuna_queries(self):
        config = get_adzuna_config({
            "adzuna": {
                "enabled": True,
                "queries": [
                    {"what": "Python", "where": "Coimbatore"},
                ],
            }
        })
        self.assertTrue(config["enabled"])
        self.assertEqual(len(config["queries"]), 1)
        self.assertEqual(config["queries"][0]["what"], "Python")
        self.assertEqual(config["queries"][0]["where"], "Coimbatore")
