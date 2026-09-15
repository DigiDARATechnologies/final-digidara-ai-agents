import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from job_agent.app import create_app


class UserDataLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(testing=True).test_client()
        self.headers = {"X-Digidara-User-Id": "learner"}

    @patch("job_agent.routes.get_db")
    def test_export_contains_profile_and_job_actions(self, get_db):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        cursor.fetchone.return_value = {
            "user_id": "learner",
            "skills": '["Python"]',
            "preferred_titles": '["Developer"]',
            "preferred_locations": "[]",
        }
        cursor.fetchall.return_value = [{"job_id": 7, "is_saved": 1, "is_hidden": 0}]
        get_db.return_value = db

        response = self.client.post(
            "/api/invoke",
            json={"action": "export_user_data", "payload": {}},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["profile"]["skills"], ["Python"])
        self.assertEqual(response.get_json()["job_actions"][0]["job_id"], 7)

    @patch("job_agent.routes.get_db")
    def test_delete_removes_database_profile_and_resume(self, get_db):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor
        cursor.fetchone.return_value = {"user_id": "learner", "resume_filename": "learner/resume.pdf"}
        get_db.return_value = db

        with tempfile.TemporaryDirectory() as directory, patch("job_agent.routes.UPLOAD_DIR", Path(directory)):
            resume = Path(directory) / "learner" / "resume.pdf"
            resume.parent.mkdir()
            resume.write_bytes(b"resume")
            response = self.client.post(
                "/api/invoke",
                json={"action": "delete_user_data", "payload": {}},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(resume.exists())
        cursor.execute.assert_any_call("DELETE FROM user_job_profiles WHERE user_id=%s", ("learner",))
        db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
