import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from cert_app.main import app
from cert_app.db.database import init_db, get_connection
from cert_app.services.auth_service import register_user, create_access_token
from cert_app.db import chat_repository
from cert_app.api.chat import rate_limiter


def _mock_mcq_questions(topic, num_questions=30):
    return [
        {
            "question": f"MCQ Question {i + 1} for {topic}?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": "Option A",
            "expected_answer": "Option A is correct.",
            "difficulty": "beginner"
        }
        for i in range(num_questions)
    ]


class TestChatAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize database and seed two separate users for ownership testing."""
        init_db()
        cls.client = TestClient(app)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # User A
            cursor.execute("SELECT id, name, email FROM users WHERE email = %s", ("chattest_user_a@example.com",))
            row_a = cursor.fetchone()
            if row_a:
                cls.user_a = row_a
            else:
                cls.user_a = register_user("Chat User A", "chattest_user_a@example.com", "Password123!")

            # User B
            cursor.execute("SELECT id, name, email FROM users WHERE email = %s", ("chattest_user_b@example.com",))
            row_b = cursor.fetchone()
            if row_b:
                cls.user_b = row_b
            else:
                cls.user_b = register_user("Chat User B", "chattest_user_b@example.com", "Password123!")
        finally:
            cursor.close()
            conn.close()

        cls.token_a = create_access_token({"sub": str(cls.user_a["id"]), "name": cls.user_a["name"], "email": cls.user_a["email"]})
        cls.headers_a = {"Authorization": f"Bearer {cls.token_a}"}

        cls.token_b = create_access_token({"sub": str(cls.user_b["id"]), "name": cls.user_b["name"], "email": cls.user_b["email"]})
        cls.headers_b = {"Authorization": f"Bearer {cls.token_b}"}

    def setUp(self):
        """Reset rate limiter before each test run."""
        rate_limiter.reset()

    @patch("cert_app.services.chat_orchestrator.generate_questions", side_effect=_mock_mcq_questions)
    def test_start_chat_session(self, mock_gen):
        """1. POST /api/chat/start creates session and returns session_id."""
        response = self.client.post(
            "/api/chat/start",
            json={"topic": "Python Web"},
            headers=self.headers_a
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("session_id", data)
        self.assertEqual(len(data["session_id"]), 36)

    @patch("cert_app.services.chat_orchestrator.generate_questions", side_effect=_mock_mcq_questions)
    def test_send_message_streaming_sse(self, mock_gen):
        """2. POST /api/chat/message streams Server-Sent Events (SSE)."""
        # Start session
        start_res = self.client.post("/api/chat/start", json={"topic": "FastAPI"}, headers=self.headers_a)
        session_id = start_res.json()["session_id"]

        # Send message
        msg_res = self.client.post(
            "/api/chat/message",
            json={"session_id": session_id, "message": "FastAPI Framework"},
            headers=self.headers_a
        )
        self.assertEqual(msg_res.status_code, 200)
        self.assertIn("text/event-stream", msg_res.headers["content-type"])
        body = msg_res.text
        self.assertIn("event: message", body)
        self.assertIn("event: status", body)

        # GET session history
        sess_res = self.client.get(f"/api/chat/session/{session_id}", headers=self.headers_a)
        self.assertEqual(sess_res.status_code, 200)
        history_data = sess_res.json()
        self.assertEqual(history_data["session"]["id"], session_id)
        self.assertGreater(len(history_data["messages"]), 0)

    @patch("cert_app.services.chat_orchestrator.generate_questions", side_effect=_mock_mcq_questions)
    def test_session_ownership_403(self, mock_gen):
        """3. User B attempting to access User A's session returns HTTP 403 Forbidden."""
        # Create session under User A
        start_res = self.client.post("/api/chat/start", json={"topic": "Security"}, headers=self.headers_a)
        session_id = start_res.json()["session_id"]

        # User B tries to send a message to User A's session
        msg_res = self.client.post(
            "/api/chat/message",
            json={"session_id": session_id, "message": "Unauthorized attempt"},
            headers=self.headers_b
        )
        self.assertEqual(msg_res.status_code, 403)
        self.assertIn("Access denied", msg_res.json()["detail"])

        # User B tries to fetch User A's session history
        get_res = self.client.get(f"/api/chat/session/{session_id}", headers=self.headers_b)
        self.assertEqual(get_res.status_code, 403)
        self.assertIn("Access denied", get_res.json()["detail"])

    @patch("cert_app.services.chat_orchestrator.generate_questions", side_effect=_mock_mcq_questions)
    def test_rate_limiting_429(self, mock_gen):
        """4. Exceeding 20 requests per minute triggers HTTP 429 Too Many Requests."""
        start_res = self.client.post("/api/chat/start", json={"topic": "Rate Limit Test"}, headers=self.headers_a)
        session_id = start_res.json()["session_id"]

        # Send 20 requests (allowed)
        for i in range(20):
            res = self.client.post(
                "/api/chat/message",
                json={"session_id": session_id, "message": f"Message {i}"},
                headers=self.headers_a
            )
            self.assertEqual(res.status_code, 200, f"Request {i+1} failed with status {res.status_code}")

        # The 21st request must trigger HTTP 429
        limit_res = self.client.post(
            "/api/chat/message",
            json={"session_id": session_id, "message": "Request 21 - limit exceeded"},
            headers=self.headers_a
        )
        self.assertEqual(limit_res.status_code, 429)
        self.assertIn("Rate limit exceeded", limit_res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
