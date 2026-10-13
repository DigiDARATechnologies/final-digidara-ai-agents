"""Phase 2 readiness skill: get_student_summary through /api/invoke."""
import os
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-unused")

import db  # noqa: E402
from app import app  # noqa: E402

HEADERS = {"X-DigiDARA-User-ID": "platform-user-1"}


def interview(score, ended, strengths='["Clear structure"]', weaknesses="Edge cases; Time complexity"):
    return {
        "overall_score": Decimal(score), "technical_accuracy": Decimal("6.0"),
        "communication_clarity": Decimal("8.0"), "confidence": None,
        "strengths": strengths, "weaknesses": weaknesses, "ended_at": ended, "difficulty": "beginner",
    }


class StudentSummaryTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def invoke(self, headers=HEADERS):
        return self.client.post("/api/invoke", json={"action": "get_student_summary", "payload": {"email": "a@b.com"}}, headers=headers)

    def test_requires_verified_identity(self):
        self.assertEqual(self.invoke(headers={}).status_code, 401)

    def test_unknown_learner_has_no_score(self):
        with patch.object(db, "query", return_value=(None, None)):
            body = self.invoke().get_json()
        self.assertIsNone(body["score"])
        self.assertEqual(body["schema"], "digidara.student_summary.v1")

    def test_scores_the_latest_completed_interviews_out_of_100(self):
        rows = [interview("8.0", datetime(2026, 10, 2)), interview("6.0", datetime(2026, 10, 1))]

        def fake_query(sql, params=None, fetch=False, fetchone=False):
            if sql.startswith("SELECT id FROM students"):
                return {"id": 7}, None
            return rows, None

        with patch.object(db, "query", side_effect=fake_query):
            body = self.invoke().get_json()
        self.assertEqual(body["score"], 70.0)
        self.assertEqual(body["activity_count"], 2)
        self.assertEqual(body["strengths"], ["Clear structure"])
        self.assertEqual(body["gaps"], ["Edge cases", "Time complexity"])
        self.assertEqual(body["metrics"]["technical_accuracy"], 60.0)
        self.assertIsNone(body["metrics"]["confidence"])
        self.assertTrue(body["last_activity_at"].startswith("2026-10-02"))
        # Both were Beginner interviews: (80 + 60) / 5 at the easy level.
        self.assertEqual(body["level_scores"], {"easy": 28.0, "medium": 0.0, "hard": 0.0})


if __name__ == "__main__":
    unittest.main()
