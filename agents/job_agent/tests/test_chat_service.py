import json
import unittest
from unittest.mock import MagicMock, patch

from job_agent.app import create_app
from job_agent.chat_service import (
    _apply_profile_updates,
    _get_user_profile_and_missing,
    _rule_based_fallback,
    chat_with_job_agent,
)


class ChatServiceUnitTests(unittest.TestCase):
    def test_get_user_profile_and_missing_identifies_empty_fields(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "user_id": "test_user_1",
            "full_name": "Karthik",
            "skills": "[]",
            "preferred_titles": "[]",
            "preferred_locations": "[]",
            "preferred_work_mode": "",
            "experience_years": 0,
            "resume_original_name": "",
            "profile_completed": 0,
            "plan_tier": "free",
        }

        profile, missing = _get_user_profile_and_missing(cursor, "test_user_1")
        self.assertEqual(profile["full_name"], "Karthik")
        self.assertIn("skills", missing)
        self.assertTrue(any("locations" in m for m in missing))
        self.assertTrue(any("resume" in m for m in missing))

    def test_apply_profile_updates_merges_new_skills_and_locations(self):
        db = MagicMock()
        cursor = MagicMock()
        current_profile = {
            "full_name": "Ananya",
            "skills": ["Python"],
            "preferred_titles": ["Backend Developer"],
            "preferred_locations": ["Chennai"],
            "preferred_work_mode": "hybrid",
            "experience_years": 1.0,
            "resume_original_name": "",
        }
        updates = {
            "skills_to_add": ["React", "FastAPI"],
            "locations_to_set": ["Chennai", "Coimbatore"],
            "experience_years": 2.0,
        }

        updated, changed = _apply_profile_updates(db, cursor, "test_user_2", current_profile, updates)
        self.assertIn("React", updated["skills"])
        self.assertIn("FastAPI", updated["skills"])
        self.assertEqual(updated["preferred_locations"], ["Chennai", "Coimbatore"])
        self.assertEqual(updated["experience_years"], 2.0)
        self.assertIn("skills", changed)
        self.assertIn("preferred locations", changed)
        self.assertIn("years of experience", changed)
        db.commit.assert_called_once()

    def test_rule_based_fallback_application_congratulations(self):
        profile = {
            "full_name": "Dhanush Kumar",
            "skills": ["Python", "React"],
            "preferred_titles": ["Software Engineer"],
            "preferred_locations": ["Chennai"],
        }
        matched_jobs = [
            {"id": 1, "title": "React Engineer", "company": "TechCorp", "location": "Chennai", "match_score": 95}
        ]

        res = _rule_based_fallback("I applied to the React Engineer role", profile, [], matched_jobs)
        self.assertIn("🎉", res["reply"])
        self.assertIn("Congratulations, Dhanush", res["reply"])
        self.assertIn("suggested_actions", res)

    def test_rule_based_fallback_extracts_skills_and_locations(self):
        profile = {
            "full_name": "Suresh",
            "skills": ["Python"],
            "preferred_titles": [],
            "preferred_locations": [],
        }
        matched_jobs = []

        res = _rule_based_fallback("I want jobs in Coimbatore with React and Docker", profile, ["skills"], matched_jobs)
        updates = res.get("profile_updates", {})
        self.assertTrue(any("React" in s for s in updates.get("skills_to_add", [])))
        self.assertTrue(any("Coimbatore" in loc for loc in updates.get("locations_to_set", [])))

    def test_rule_based_fallback_answers_salary_and_experience_for_focused_job(self):
        profile = {"full_name": "Dhanush", "skills": ["Python"], "experience_years": 0}
        focused_job = {
            "id": 55,
            "title": "Python with Spark Developer (5.1-7 years)-Chennai",
            "company": "Capco",
            "apply_url": "https://example.com/apply/capco",
            "salary_text": "₹8,00,000 - ₹12,00,000",
            "experience_min": 5,
            "experience_max": 7,
            "description": "Capco is hiring Python Spark developers.",
        }

        # Test salary inquiry
        res_salary = _rule_based_fallback(
            "what is the salary in this job?", profile, [], [], focused_job=focused_job
        )
        self.assertIn("Capco", res_salary["reply"])
        self.assertIn("₹8,00,000", res_salary["reply"])
        self.assertIn("[Apply on Employer Portal](https://example.com/apply/capco)", res_salary["reply"])

        # Test experience inquiry
        res_exp = _rule_based_fallback(
            "what is the experience in this job?", profile, [], [], focused_job=focused_job
        )
        self.assertIn("5.1-7 years", res_exp["reply"])
        self.assertIn("Capco", res_exp["reply"])
        self.assertIn("[Apply on Employer Portal](https://example.com/apply/capco)", res_exp["reply"])

    def test_rule_based_fallback_answers_trust_and_authenticity(self):
        profile = {"full_name": "Dhanush", "skills": ["React"], "experience_years": 0}
        focused_job = {
            "id": 99,
            "title": "Junior React Developer",
            "company": "Freshworks",
            "apply_url": "https://jobs.lever.co/freshworks/123",
            "trust_score": 96,
            "trust_badge": "🛡️ Verified Corporate Posting",
            "signals": ["Verified enterprise ATS / official job portal", "Named employer: Freshworks"],
        }

        res = _rule_based_fallback("is this job genuine and trusted?", profile, [], [], focused_job=focused_job)
        self.assertIn("🛡️ Verified Corporate Posting", res["reply"])
        self.assertIn("96%", res["reply"])
        self.assertIn("[Apply on Employer Portal]", res["reply"])


class ChatEndpointIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(testing=True).test_client()
        self.headers = {"X-Digidara-User-Id": "test_learner"}

    @patch("job_agent.chat_service.get_db")
    def test_invoke_chat_returns_reply_and_profile(self, get_db):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor

        cursor.fetchone.return_value = {
            "user_id": "test_learner",
            "full_name": "Deepak",
            "skills": '["Python", "Django"]',
            "preferred_titles": '["Python Developer"]',
            "preferred_locations": '["Chennai"]',
            "preferred_work_mode": "remote",
            "experience_years": 1,
            "resume_original_name": "deepak_resume.pdf",
            "profile_completed": 1,
            "plan_tier": "free",
        }
        cursor.fetchall.return_value = [
            {
                "id": 101,
                "title": "Junior Python Developer",
                "company": "Cognizant",
                "location": "Chennai",
                "work_mode": "hybrid",
                "apply_url": "https://example.com/apply",
                "description": "Looking for Python/Django skills",
                "skills": '["Python", "Django"]',
                "category": "software_engineering",
                "external_id": "adzuna:101",
            }
        ]
        get_db.return_value = db

        response = self.client.post(
            "/api/invoke",
            json={"action": "chat", "payload": {"message": "Can you show me Python jobs in Chennai?"}},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("reply", data)
        self.assertIn("updated_profile", data)
        self.assertIn("matched_jobs", data)
        self.assertTrue(len(data["matched_jobs"]) > 0)
        self.assertEqual(data["matched_jobs"][0]["id"], 101)


if __name__ == "__main__":
    unittest.main()
