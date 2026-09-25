import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from job_agent.app import create_app
from job_agent.skills import (
    extract_skills_from_text,
    extract_text_from_resume_file,
    parse_resume_for_profile,
)
from job_agent.chat_service import chat_with_job_agent


class ProductionEnhancementsTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(testing=True)
        self.client = self.app.test_client()
        self.headers = {
            "X-Digidara-User-Id": "test_learner_123",
            "X-Digidara-Is-Admin": "false",
        }

    def test_location_filtering_in_feed(self):
        with patch("job_agent.routes.get_db") as mock_db:
            db = MagicMock()
            cursor = MagicMock()
            db.cursor.return_value = cursor

            # Mock user profile
            cursor.fetchone.return_value = {
                "user_id": "test_learner_123",
                "full_name": "Test Learner",
                "skills": '["Python", "FastAPI"]',
                "preferred_titles": '["Software Engineer"]',
                "preferred_locations": '["Coimbatore"]',
                "preferred_work_mode": "remote",
                "experience_years": 0.0,
                "plan_tier": "free",
            }

            # Mock matching jobs in Coimbatore
            cursor.fetchall.return_value = [
                {
                    "id": 1,
                    "title": "Junior Python Developer",
                    "company": "Tech Solutions",
                    "location": "Coimbatore, Tamil Nadu",
                    "location_district": "Coimbatore",
                    "location_region": "Kongu",
                    "work_mode": "onsite",
                    "employment_type": "Full Time",
                    "skills": '["Python", "SQL"]',
                    "apply_url": "https://example.com/apply",
                    "status": "active",
                    "published_at": "2026-09-24 10:00:00",
                }
            ]
            mock_db.return_value = db

            with patch("job_agent.routes.check_and_record_feed_usage") as mock_usage:
                mock_usage.return_value = {
                    "insufficient_tokens": False,
                    "jobs_served": 1,
                    "free_quota_remaining": 19,
                    "total_viewed_today": 1,
                    "free_daily_limit": 20,
                    "tokens_charged": 0,
                }

                # Query with location=Coimbatore
                resp = self.client.get(
                    "/api/jobs/me/feed?location=Coimbatore",
                    headers=self.headers,
                )
                self.assertEqual(resp.status_code, 200)
                data = resp.get_json()
                self.assertIn("jobs", data)
                self.assertEqual(len(data["jobs"]), 1)
                self.assertEqual(data["jobs"][0]["location_district"], "Coimbatore")

                # Verify SQL jobs query included location filter
                executed_jobs_query = cursor.execute.call_args_list[1][0][0]
                self.assertIn("location", executed_jobs_query.lower())

    def test_application_status_update_lifecycle(self):
        with patch("job_agent.routes.get_db") as mock_db:
            db = MagicMock()
            cursor = MagicMock()
            db.cursor.return_value = cursor
            cursor.fetchone.return_value = {"id": 42, "status": "active"}
            mock_db.return_value = db

            # 1. Update status to 'screening'
            resp = self.client.put(
                "/api/jobs/me/applications/42/status",
                headers=self.headers,
                json={"status": "screening"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data["application_status"], "screening")

            # 2. Update status to 'interview'
            resp = self.client.put(
                "/api/jobs/me/applications/42/status",
                headers=self.headers,
                json={"status": "interview"},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json()["application_status"], "interview")

            # 3. Reject invalid status
            resp = self.client.put(
                "/api/jobs/me/applications/42/status",
                headers=self.headers,
                json={"status": "invalid_status_xyz"},
            )
            self.assertEqual(resp.status_code, 400)
            self.assertIn("Invalid application status", resp.get_json()["error"])

    def test_invoke_gateway_update_application_status(self):
        with patch("job_agent.routes.get_db") as mock_db:
            db = MagicMock()
            cursor = MagicMock()
            db.cursor.return_value = cursor
            cursor.fetchone.return_value = {"id": 101, "status": "active"}
            mock_db.return_value = db

            resp = self.client.post(
                "/api/invoke",
                headers=self.headers,
                json={
                    "action": "update_application_status",
                    "payload": {"job_id": 101, "status": "offer"},
                },
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json()["application_status"], "offer")

    def test_resume_text_and_skills_parsing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sample_txt = Path(temp_dir) / "sample_resume.txt"
            sample_txt.write_text(
                "John Doe\nSummary: Software Engineer with 2 years of experience in Python, React, Docker, and PostgreSQL.",
                encoding="utf-8",
            )

            parsed = parse_resume_for_profile(sample_txt)
            self.assertIn("Python", parsed["skills"])
            self.assertIn("React", parsed["skills"])
            self.assertIn("Docker", parsed["skills"])
            self.assertIn("PostgreSQL", parsed["skills"])
            self.assertEqual(parsed["experience_years"], 2.0)

    def test_openai_api_chat_call_and_fallback(self):
        with patch("job_agent.chat_service.get_db") as mock_db, \
             patch("requests.post") as mock_post, \
             patch("job_agent.chat_service.OPENAI_API_KEY", "fake-openai-key"):
            db = MagicMock()
            cursor = MagicMock()
            db.cursor.return_value = cursor
            cursor.fetchone.return_value = {
                "user_id": "test_learner_123",
                "full_name": "Test Learner",
                "skills": '["Python"]',
                "preferred_titles": '["Developer"]',
                "preferred_locations": '["Chennai"]',
                "preferred_work_mode": "remote",
                "experience_years": 0.0,
                "resume_original_name": "",
                "profile_completed": 1,
                "plan_tier": "starter",
            }
            cursor.fetchall.return_value = []
            mock_db.return_value = db

            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "reply": "Here are entry-level Python roles in Chennai.",
                                "show_jobs": True,
                                "profile_updates": {"skills_to_add": ["FastAPI"]},
                                "suggested_actions": [],
                            })
                        }
                    }
                ]
            }

            res = chat_with_job_agent(
                user_id="test_learner_123",
                message="Find Python jobs",
            )
            self.assertIsNotNone(res)
            self.assertIn("Python roles", res["reply"])
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            self.assertEqual(args[0], "https://api.openai.com/v1/chat/completions")
            self.assertIn("Bearer fake-openai-key", kwargs["headers"]["Authorization"])


if __name__ == "__main__":
    unittest.main()
