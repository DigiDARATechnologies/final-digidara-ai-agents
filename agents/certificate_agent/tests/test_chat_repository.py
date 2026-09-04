import unittest
import time
from cert_app.db.database import init_db, get_connection
from cert_app.services.auth_service import register_user
from cert_app.db import chat_repository


class TestChatRepository(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize DB tables and create a dummy user for foreign key relations."""
        init_db()
        # Register a test user if not already present
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id FROM users WHERE email = %s", ("test_chat_user@example.com",))
            row = cursor.fetchone()
            if row:
                cls.user_id = row["id"]
            else:
                user = register_user("Test Chat User", "test_chat_user@example.com", "Password123!")
                cls.user_id = user["id"]
        finally:
            cursor.close()
            conn.close()

    def test_create_and_get_session(self):
        session_id = chat_repository.create_session(self.user_id, "FastAPI Deep Dive", total_questions=10)
        self.assertIsNotNone(session_id)
        self.assertEqual(len(session_id), 36)

        session = chat_repository.get_session(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session["id"], session_id)
        self.assertEqual(session["user_id"], self.user_id)
        self.assertEqual(session["topic"], "FastAPI Deep Dive")
        self.assertEqual(session["status"], "onboarding")
        self.assertEqual(session["total_questions"], 10)
        self.assertEqual(session["current_question_index"], 0)
        self.assertIsNone(session["score"])
        self.assertIsNotNone(session["started_at"])
        self.assertIsNone(session["completed_at"])

    def test_update_session_status(self):
        session_id = chat_repository.create_session(self.user_id, "Docker Security", total_questions=5)

        # Move to in_exam
        updated = chat_repository.update_session_status(session_id, "in_exam", current_question_index=3)
        self.assertTrue(updated)

        sess = chat_repository.get_session(session_id)
        self.assertEqual(sess["status"], "in_exam")
        self.assertEqual(sess["current_question_index"], 3)
        self.assertIsNone(sess["completed_at"])

        # Complete session with score
        updated = chat_repository.update_session_status(session_id, "completed", score=90.0)
        self.assertTrue(updated)

        sess = chat_repository.get_session(session_id)
        self.assertEqual(sess["status"], "completed")
        self.assertEqual(sess["score"], 90.0)
        self.assertIsNotNone(sess["completed_at"])

    def test_append_message_and_get_history(self):
        session_id = chat_repository.create_session(self.user_id, "AsyncIO Masterclass", total_questions=2)

        # 1. Append system message
        msg1 = chat_repository.append_message(
            session_id=session_id,
            role="system",
            content="Welcome to the AsyncIO Masterclass Exam!",
            message_type="text"
        )
        self.assertEqual(msg1["role"], "system")
        self.assertEqual(msg1["content"], "Welcome to the AsyncIO Masterclass Exam!")

        # 2. Append assistant question message with metadata
        question_meta = {
            "question_index": 1,
            "options": ["A. Task", "B. Thread", "C. Process", "D. Future"],
            "correct_answer": "A. Task"
        }
        msg2 = chat_repository.append_message(
            session_id=session_id,
            role="assistant",
            content="Question 1: Which object represents an event loop coroutine?",
            message_type="mcq_question",
            metadata=question_meta
        )
        self.assertEqual(msg2["message_type"], "mcq_question")
        self.assertEqual(msg2["metadata"], question_meta)

        # 3. Append user answer message
        answer_meta = {"score_delta": 1}
        msg3 = chat_repository.append_message(
            session_id=session_id,
            role="user",
            content="A. Task",
            message_type="mcq_answer",
            metadata=answer_meta
        )
        self.assertEqual(msg3["role"], "user")
        self.assertEqual(msg3["message_type"], "mcq_answer")

        # Fetch message history
        history = chat_repository.get_message_history(session_id)
        self.assertEqual(len(history), 3)

        # Verify ordering and content
        self.assertEqual(history[0]["role"], "system")
        self.assertEqual(history[0]["content"], "Welcome to the AsyncIO Masterclass Exam!")

        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["message_type"], "mcq_question")
        self.assertEqual(history[1]["metadata"]["correct_answer"], "A. Task")

        self.assertEqual(history[2]["role"], "user")
        self.assertEqual(history[2]["message_type"], "mcq_answer")
        self.assertEqual(history[2]["metadata"]["score_delta"], 1)

    def test_invalid_arguments(self):
        session_id = chat_repository.create_session(self.user_id, "Error Handling")
        
        with self.assertRaises(ValueError):
            chat_repository.update_session_status(session_id, "invalid_status_enum")

        with self.assertRaises(ValueError):
            chat_repository.append_message(session_id, "invalid_role", "Hello")

        with self.assertRaises(ValueError):
            chat_repository.append_message(session_id, "user", "Hello", message_type="invalid_type")


if __name__ == "__main__":
    unittest.main()
