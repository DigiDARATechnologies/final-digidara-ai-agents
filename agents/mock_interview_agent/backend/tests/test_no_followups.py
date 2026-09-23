"""The planned question count cannot grow while answers are submitted."""

import json
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from app import create_app
from scoring import build_scorecard


class PlannedQuestionFlowTests(unittest.TestCase):
    def test_ten_answers_produce_ten_verdicts_and_scorecard_entries(self):
        client = create_app().test_client()
        interview = {
            "id": 91, "student_id": 1, "round_type": "technical",
            "subject": "Python", "difficulty": "beginner",
            "num_questions": 10, "status": "in_progress", "interview_mode": "course",
        }
        rows = [{
            "id": order, "interview_id": 91, "question_order": order,
            "question": f"What is concept {order}?", "question_source": "ai_generated",
            "topic_area": "fundamentals", "subject_tag": "Python",
            "is_followup": False, "answer": None, "verdict": None,
            "verdict_reason": None, "ideal_answer": None,
            "timed_out": False, "time_taken_sec": None,
            "answer_audio_path": None, "processing_status": "question_ready",
        } for order in range(1, 11)]

        def query(sql, params=None, fetch=False, fetchone=False):
            compact = " ".join(sql.split())
            if compact.startswith("SELECT * FROM interview_details") and "question_order = %s" in compact:
                return next((row.copy() for row in rows if row["question_order"] == params[1]), None), 0
            if compact.startswith("SELECT * FROM interviews"):
                return interview.copy(), 0
            if "question_order > %s" in compact:
                return next((row.copy() for row in rows if row["question_order"] > params[1] and not row["is_followup"]), None), 0
            if compact.startswith("SELECT * FROM interview_details"):
                return [row.copy() for row in rows], 0
            if compact.startswith("SELECT question_order, id, question") or compact.startswith("SELECT id, question_order, question"):
                return [row.copy() for row in rows], 0
            if compact.startswith("UPDATE interview_details SET verdict="):
                verdict, reason, ideal, row_id = params
                rows[row_id - 1].update(verdict=verdict, verdict_reason=reason, ideal_answer=ideal)
            if compact.startswith("UPDATE interviews SET"):
                interview["status"] = "completed"
            if compact.startswith("SELECT request_type"):
                return [], 0
            return None, 0

        def save_answer(row_id, _student_id, _day, answer, time_taken, *_args, **_kwargs):
            rows[row_id - 1].update(answer=answer, time_taken_sec=time_taken)
            return {"saved": True, "limit_reached": False, "answered_count": row_id}

        evaluations = [{
            "question_id": order,
            "verdict": "wrong" if order % 2 else "correct",
            "reason": "Evaluated.", "ideal_answer": "A useful explanation.",
        } for order in range(1, 11)]
        summary = {
            "overall_score": 5, "technical_accuracy": 5,
            "communication_clarity": 5, "confidence": 5,
            "strengths": json.dumps(["Relevant", "Clear"]),
            "weaknesses": json.dumps(["Accuracy", "Detail"]),
            "feedback": "Keep practising.",
        }
        with (
            patch("routes.answers.db.query", side_effect=query),
            patch("routes.answers.db.save_answer_with_optional_daily_usage", side_effect=save_answer),
            patch("routes.answers.daily_answered_count", return_value=0),
            patch("routes.answers.groq_client.evaluate_answer") as immediate_evaluation,
            patch("routes.interviews._batch_evaluations_or_error", return_value=(evaluations, None)) as batch,
            patch("routes.interviews.groq_client.evaluate_interview", return_value=summary),
            patch("routes.interviews.finalize_open_focus_events", return_value={}),
            patch("routes.interviews.track_ai_usage", side_effect=lambda **_kwargs: nullcontext()),
        ):
            for order in range(1, 11):
                response = client.post("/api/submit_answer", json={
                    "interview_id": 91, "question_order": order,
                    "answer": "Correct concept." if order % 2 == 0 else "I do not know.",
                    "time_taken_sec": 4,
                })
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertEqual(response.get_json()["done"], order == 10)
                if order < 10:
                    self.assertEqual(response.get_json()["question_order"], order + 1)
                    self.assertFalse(response.get_json()["is_followup"])
            result = client.post("/api/end_interview", json={"interview_id": 91})

        self.assertEqual(result.status_code, 200, result.get_json())
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(not row["is_followup"] and row["verdict"] for row in rows))
        self.assertEqual(len(result.get_json()["scorecard"]), 10)
        self.assertEqual(batch.call_count, 1)
        immediate_evaluation.assert_not_called()

    def test_historical_followup_still_renders_below_parent(self):
        rows = [
            {"question": "Original?", "answer": "First answer", "is_followup": False,
             "verdict": "partial", "verdict_reason": "Incomplete", "ideal_answer": "Original ideal"},
            {"question": "Old follow-up?", "answer": "Clarified answer", "is_followup": True,
             "verdict": "correct", "verdict_reason": "Clarified", "ideal_answer": "Follow-up ideal"},
        ]
        scorecard, marks, maximum = build_scorecard(rows)
        self.assertEqual((len(scorecard), marks, maximum), (1, 1, 1))
        self.assertEqual(scorecard[0]["followup"]["question"], "Old follow-up?")
        self.assertEqual(scorecard[0]["verdict"], "correct")


if __name__ == "__main__":
    unittest.main()
