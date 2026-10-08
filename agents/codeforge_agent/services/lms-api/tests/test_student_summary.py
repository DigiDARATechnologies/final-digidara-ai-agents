"""Phase 2 readiness skill: get_student_summary."""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lms_api.app import create_app  # noqa: E402
from lms_api.readiness import build_student_summary  # noqa: E402

HEADERS = {"X-DigiDARA-User-Id": "platform-user-1"}


def row(difficulty, score, status, topic="Arrays", day=1):
    return {"difficulty": difficulty, "best_score": score, "status": status, "topic": topic, "updated_at": datetime(2026, 10, day)}


class SummaryRepository:
    def __init__(self, rows):
        self.rows = rows
        self.emails = []

    def student_problem_rows(self, email):
        self.emails.append(email)
        return self.rows


class StudentSummaryScoringTests(unittest.TestCase):
    def test_no_attempts_has_no_score(self):
        self.assertIsNone(build_student_summary([row("Easy", 0, "Not Started")])["score"])

    def test_hard_problems_weigh_more_and_breadth_scales_the_score(self):
        body = build_student_summary([row("Easy", 100, "Solved"), row("Hard", 50, "Attempted", topic="Graphs", day=3)])
        # quality (100*1 + 50*3) / 4 = 62.5; one solve -> breadth 0.5 + 0.5 * 1/20 = 0.525
        self.assertEqual(body["score"], 32.8)
        self.assertEqual(body["metrics"]["problems_solved"], 1)
        self.assertEqual(body["strengths"], ["Arrays (1 solved)"])
        self.assertEqual(body["gaps"], ["Graphs (1 unsolved)"])
        self.assertTrue(body["last_activity_at"].startswith("2026-10-03"))

    def test_twenty_solves_give_full_breadth(self):
        body = build_student_summary([row("Medium", 100, "Solved") for _ in range(20)])
        self.assertEqual(body["score"], 100.0)


class StudentSummaryActionTests(unittest.TestCase):
    def setUp(self):
        self.repo = SummaryRepository([row("Easy", 100, "Solved")])
        app = create_app({"TESTING": True, "LMS_API_SHARED_SECRET": "s", "CODING_PRACTICE_ENABLED": True}, self.repo)
        self.client = app.test_client()

    def invoke(self, headers=HEADERS, email="Student@Example.com"):
        return self.client.post("/api/invoke", json={"action": "get_student_summary", "payload": {"email": email}}, headers=headers)

    def test_requires_verified_identity(self):
        self.assertEqual(self.invoke(headers={}).status_code, 401)

    def test_reads_the_verified_learners_rows(self):
        body = self.invoke().get_json()
        self.assertEqual(self.repo.emails, ["student@example.com"])
        self.assertEqual(body["schema"], "digidara.student_summary.v1")
        self.assertEqual(body["activity_count"], 1)


if __name__ == "__main__":
    unittest.main()
