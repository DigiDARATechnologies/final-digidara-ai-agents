import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from job_agent.providers.apify import normalize_job, run_actor_and_fetch_items
from job_agent.providers.config_loader import get_apify_config


class LinkedInApifyNormalizerTests(unittest.TestCase):
    def test_documented_linkedin_actor_shape_maps_to_canonical_job(self):
        job = normalize_job(
            {
                "jobId": "3812345678",
                "title": "Junior Software Engineer",
                "company": "Example Co",
                "location": "Chennai, Tamil Nadu, India",
                "listingDateParsed": "2026-09-09T08:30:00.000Z",
                "jobUrl": "https://www.linkedin.com/jobs/view/3812345678",
            },
            "linkedin",
        )

        self.assertEqual(job["external_id"], "3812345678")
        self.assertEqual(job["apply_url"], "https://www.linkedin.com/jobs/view/3812345678")
        self.assertIsInstance(job["published_at"], datetime)

    def test_linkedin_record_missing_required_url_is_rejected(self):
        self.assertIsNone(normalize_job({"jobId": "1", "title": "Developer", "company": "Example"}, "linkedin"))

    @patch("job_agent.providers.apify._token", return_value="test-token")
    def test_actor_owner_slash_name_uses_apify_api_identifier(self, _token):
        session = MagicMock()
        response = MagicMock(status_code=200)
        response.json.return_value = []
        session.post.return_value = response

        run_actor_and_fetch_items("artificially/linkedin-jobs-scraper", {"maxJobs": 1}, session=session)

        self.assertIn("artificially~linkedin-jobs-scraper", session.post.call_args.args[0])

    @patch.dict("os.environ", {"APIFY_LINKEDIN_ACTOR_ID": "owner/selected-by-env"}, clear=False)
    def test_linkedin_actor_id_can_be_selected_by_environment(self):
        config = get_apify_config({"apify": {"enabled": True, "actors": [
            {"platform": "linkedin", "actor_id": "owner/default", "enabled": True}
        ]}})
        self.assertEqual(config["actors"][0]["actor_id"], "owner/selected-by-env")
