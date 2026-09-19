"""Strategy F invoke adapter: identity gate and student-id substitution."""
import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-unused")

import db  # noqa: E402
from app import app  # noqa: E402
from session_auth import issue_session_token  # noqa: E402


class InvokeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def invoke(self, action, payload=None, headers=None):
        return self.client.post(
            "/api/invoke", json={"action": action, "payload": payload or {}}, headers=headers or {},
        )

    def test_health(self):
        response = self.invoke("health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["agent_name"], "mock_interview_agent")

    def test_ensure_session_requires_verified_identity(self):
        response = self.invoke("ensure_session", {"user_id": "u1", "email": "a@b.com"})
        self.assertEqual(response.status_code, 401)

    def test_ensure_session_rejects_mismatched_identity(self):
        response = self.invoke(
            "ensure_session", {"user_id": "someone-else", "email": "a@b.com"},
            headers={"X-DigiDARA-User-ID": "u1"},
        )
        self.assertEqual(response.status_code, 401)

    def test_ensure_session_creates_student_and_issues_token(self):
        with patch.object(db, "query", side_effect=[(None, None), (None, 42)]):
            response = self.invoke(
                "ensure_session", {"user_id": "u1", "email": "A@B.com", "name": "Alice"},
                headers={"X-DigiDARA-User-ID": "u1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["student_id"], 42)
        self.assertTrue(response.get_json()["sessionToken"])

    def test_student_scoped_actions_require_token(self):
        self.assertEqual(self.invoke("profile").status_code, 401)
        self.assertEqual(self.invoke("dashboard", {"sessionToken": "garbage"}).status_code, 401)

    def test_client_supplied_student_id_is_ignored(self):
        token = issue_session_token(42)
        internal = MagicMock()
        internal.get.return_value = MagicMock(status_code=200)
        with patch.object(app, "test_client", return_value=internal):
            self.invoke("profile", {"sessionToken": token, "student_id": 999})
        self.assertEqual(internal.get.call_args.args[0], "/api/profile/42")

    def test_start_interview_overrides_payload_student_id(self):
        token = issue_session_token(42)
        internal = MagicMock()
        internal.open.return_value = MagicMock(status_code=200)
        with patch.object(app, "test_client", return_value=internal):
            self.invoke("start_interview", {"sessionToken": token, "student_id": 999, "round_type": "hr"})
        self.assertEqual(internal.open.call_args.kwargs["json"]["student_id"], 42)

    def test_other_students_interview_is_not_found(self):
        token = issue_session_token(42)
        internal = MagicMock()
        with patch.object(app, "test_client", return_value=internal), \
                patch.object(db, "query", return_value=({"student_id": 7}, None)):
            response = self.invoke("submit_answer", {"sessionToken": token, "interview_id": 5, "question_order": 1, "answer": "x"})
        self.assertEqual(response.status_code, 404)
        internal.open.assert_not_called()

    def test_own_interview_is_forwarded(self):
        token = issue_session_token(42)
        internal = MagicMock()
        internal.open.return_value = MagicMock(status_code=200)
        with patch.object(app, "test_client", return_value=internal), \
                patch.object(db, "query", return_value=({"student_id": 42}, None)):
            self.invoke("end_interview", {"sessionToken": token, "interview_id": 5})
        internal.open.assert_called_once()

    def test_unknown_action(self):
        token = issue_session_token(42)
        response = self.invoke("nope", {"sessionToken": token})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "unknown_action")


if __name__ == "__main__":
    unittest.main()
