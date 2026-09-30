import unittest
from unittest.mock import patch

from cert_app.db.database import init_db, get_connection
from cert_app.services.auth_service import register_user
from cert_app.db import chat_repository
from cert_app.services import chat_orchestrator
from cert_app.services.exam_report import build_chat_exam_report
from cert_app.agents.question_agent import QuestionDeduper, _protect_code_in_text, is_practical_data_topic


def _questions(topic, num_questions=30, difficulty="mixed", **kwargs):
    return [
        {
            "question": f"Report question {i + 1} about {topic}?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_answer": "Option A",
            "expected_answer": "Option A is the correct choice.",
            "difficulty": "beginner",
        }
        for i in range(num_questions)
    ]


def _sync_runner(fn, *args, **kwargs):
    fn(*args, **kwargs)


class TestExamReportAndFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id FROM users WHERE email = %s", ("report_test_user@example.com",))
            row = cursor.fetchone()
            cls.user_id = row["id"] if row else register_user(
                "Report Test User", "report_test_user@example.com", "Password123!"
            )["id"]
        finally:
            cursor.close()
            conn.close()

    def setUp(self):
        self.p1 = patch("cert_app.services.chat_orchestrator.analyze_user_message",
                        side_effect=lambda sid, msg: {"intent": "start_exam", "topic": msg, "reply": None})
        self.p1.start()
        self.p2 = patch("cert_app.services.chat_orchestrator.generate_questions", side_effect=_questions)
        self.p2.start()

    def tearDown(self):
        self.p1.stop()
        self.p2.stop()

    def _start_exam(self, topic="Report Topic"):
        sid = chat_repository.create_session(self.user_id, "")
        chat_orchestrator.handle_message(sid, topic)
        chat_orchestrator.handle_message(sid, "Yes, start the exam")
        res = chat_orchestrator.handle_message(sid, "beginner", bg_runner=_sync_runner)
        self.assertEqual(res.session_status, "in_exam")
        return sid

    def test_failed_exam_report_and_correct_count(self):
        sid = self._start_exam()
        for i in range(30):
            res = chat_orchestrator.handle_message(sid, "Option A" if i < 3 else "Option B", question_index=i)
        self.assertEqual(res.session_status, "failed")
        self.assertEqual(res.correct_answers, 3)
        self.assertIn("3 out of 30", res.messages[0]["content"])

        pdf, filename = build_chat_exam_report(sid, self.user_id)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertTrue(filename.endswith(".pdf"))

    def test_report_refused_for_other_user_and_unfinished_exam(self):
        sid = self._start_exam()
        with self.assertRaises(ValueError):
            build_chat_exam_report(sid, self.user_id)  # still in progress
        with self.assertRaises(LookupError):
            build_chat_exam_report(sid, self.user_id + 999999)

    def test_stale_answer_is_ignored(self):
        sid = self._start_exam()
        first = chat_orchestrator.handle_message(sid, "Option A", question_index=0)
        self.assertEqual(first.current_question_index, 1)
        stale = chat_orchestrator.handle_message(sid, "Timeout", question_index=0)
        self.assertTrue(stale.stale)
        self.assertEqual(stale.messages, [])
        self.assertEqual(chat_repository.get_session(sid)["current_question_index"], 1)

    def test_keep_chatting_continues_same_session(self):
        sid = chat_repository.create_session(self.user_id, "")
        chat_orchestrator.handle_message(sid, "Docker")
        res = chat_orchestrator.handle_message(sid, "No, let's keep chatting")
        self.assertEqual(res.session_status, "onboarding")
        self.assertEqual(res.messages[0]["metadata"].get("phase"), "keep_chatting")

    def test_certificate_name_locked_to_account_name(self):
        from cert_app.services import exam_service
        cert = exam_service.issue_certificate_for_chat_session(self.user_id, "Name Lock Topic", 90.0)
        with self.assertRaises(ValueError):
            exam_service.regenerate_certificate_with_recipient_name(self.user_id, cert["certificate_id"], "Someone Else")
        ok = exam_service.regenerate_certificate_with_recipient_name(self.user_id, cert["certificate_id"], "report  TEST user")
        self.assertEqual(ok["recipient_name"], "report TEST user")


class TestQuestionHelpers(unittest.TestCase):
    def test_deduper(self):
        d = QuestionDeduper(["What is the output of print(2 ** 3) in the Python programming language?"])
        self.assertTrue(d.is_duplicate("what is the output of print(2 ** 3) in the python programming language"))
        self.assertFalse(d.is_duplicate("What is the output of print(3 ** 4) in the Python programming language?"))

    def test_code_fence_untouched_and_data_topics(self):
        text = "Output?\n```python\nprint(2 ** 3)\n```"
        self.assertEqual(_protect_code_in_text(text), text)
        self.assertTrue(is_practical_data_topic("Data Science & Analytics"))
        self.assertFalse(is_practical_data_topic("Docker"))


if __name__ == "__main__":
    unittest.main()
