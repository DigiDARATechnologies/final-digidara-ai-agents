"""HTTP-level integration tests with external AI and persistence mocked.

These tests deliberately enter through Flask's test client.  They verify that
Blueprint routing, request validation, orchestration, and response serialization
work together without making network calls or writing to a real database.
"""

import json
import unittest
from datetime import datetime
from unittest.mock import patch

from app import create_app
from runtime_state import dashboard_cache
from routes import answers as answers_routes


class RouteIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()
        dashboard_cache.invalidate(1)

    def test_start_interview_routes_request_through_atomic_creation(self):
        creation = {
            "student_exists": True,
            "created": True,
            "interview_id": 41,
            "orphaned_interview_id": None,
        }
        with (
            patch("routes.interviews.db.query", return_value=({"id": 1}, 0)),
            patch("routes.interviews.daily_answered_count", return_value=0),
            patch("routes.interviews.active_interview_payload", return_value=None),
            patch("routes.interviews.recent_questions_for_student", return_value=[]),
            patch("routes.interviews.recent_topic_areas_for_student", return_value=[]),
            patch("routes.interviews.get_recent_asked_history", return_value=(set(), [])),
            patch("routes.interviews.groq_client.infer_role_skills", return_value=[]),
            patch(
                "routes.interviews.groq_client.generate_question",
                return_value={
                    "topic_area": "generators and iterators",
                    "question": "What does a Python generator do?",
                },
            ) as generate_question,
            patch(
                "routes.interviews.db.create_or_resume_interview",
                return_value=creation,
            ) as create_interview,
        ):
            response = self.client.post(
                "/api/start_interview",
                json={
                    "student_id": 1,
                    "round_type": "technical",
                    "subject": "Python",
                    "difficulty": "beginner",
                    "num_questions": 5,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["interview_id"], 41)
        self.assertEqual(payload["question_order"], 1)
        self.assertEqual(payload["question"], "What does a Python generator do?")
        generate_question.assert_called_once()
        create_interview.assert_called_once_with(
            1,
            "technical",
            "Python",
            "beginner",
            5,
            "What does a Python generator do?",
            "generators and iterators",
            interview_mode="course",
            role_name="",
            resolved_subjects=None,
            first_subject_tag="Python",
            question_plan=None,
        )

    def test_role_start_schedules_search_without_waiting_for_it(self):
        creation = {"student_exists": True, "created": True, "interview_id": 77, "orphaned_interview_id": None}
        plan = [{"question": "What is a Python dictionary?", "topic_area": "Python fundamentals", "source": "ai_generated", "subject_tag": "python"}]
        with (
            patch.dict("os.environ", {"ENABLE_LIVE_WEB_SEARCH": "true"}),
            patch("routes.interviews.db.query", return_value=({"id": 1}, 0)),
            patch("routes.interviews.daily_answered_count", return_value=0),
            patch("routes.interviews.active_interview_payload", return_value=None),
            patch("routes.interviews.recent_questions_for_student", return_value=[]),
            patch("routes.interviews.recent_topic_areas_for_student", return_value=[]),
            patch("routes.interviews.get_recent_asked_history", return_value=(set(), [])),
            patch("routes.interviews.groq_client.resolve_role_subjects", return_value=["python"]),
            patch("routes.interviews.groq_client.infer_role_skills", return_value=["Python fundamentals"]),
            patch("routes.interviews.groq_client.build_interview_questions", return_value=plan),
            patch("routes.interviews.db.create_or_resume_interview", return_value=creation),
            patch("routes.interviews.schedule_live_question_search") as schedule,
            patch("services.background_question_search.fetch_live_real_questions") as search,
        ):
            response = self.client.post("/api/start_interview", json={
                "student_id": 1, "round_type": "technical", "interview_mode": "role",
                "role_name": "Python Fullstack Developer", "difficulty": "beginner",
                "num_questions": 10,
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["question"], plan[0]["question"])
        schedule.assert_called_once()

    def test_role_start_skips_search_when_disabled(self):
        creation = {"student_exists": True, "created": True, "interview_id": 78, "orphaned_interview_id": None}
        plan = [
            {"question": f"AI question {index}?", "topic_area": "Python fundamentals", "source": "ai_generated", "subject_tag": "python"}
            for index in range(1, 11)
        ]
        with (
            patch.dict("os.environ", {"ENABLE_LIVE_WEB_SEARCH": "false"}),
            patch("routes.interviews.db.query", return_value=({"id": 1}, 0)),
            patch("routes.interviews.daily_answered_count", return_value=0),
            patch("routes.interviews.active_interview_payload", return_value=None),
            patch("routes.interviews.recent_questions_for_student", return_value=[]),
            patch("routes.interviews.recent_topic_areas_for_student", return_value=[]),
            patch("routes.interviews.get_recent_asked_history", return_value=(set(), [])),
            patch("routes.interviews.groq_client.resolve_role_subjects", return_value=["python"]),
            patch("routes.interviews.groq_client.infer_role_skills", return_value=["Python fundamentals"]),
            patch("routes.interviews.groq_client.build_interview_questions", return_value=plan),
            patch("routes.interviews.db.create_or_resume_interview", return_value=creation),
            patch("routes.interviews.schedule_live_question_search") as schedule,
            patch("services.background_question_search.fetch_live_real_questions") as search,
        ):
            response = self.client.post("/api/start_interview", json={
                "student_id": 1, "round_type": "technical", "interview_mode": "role",
                "role_name": "Python Fullstack Developer", "difficulty": "beginner",
                "num_questions": 10,
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["question"], plan[0]["question"])
        self.assertEqual(len(plan), 10)
        self.assertTrue(all(item["source"] == "ai_generated" for item in plan))
        schedule.assert_not_called()
        search.assert_not_called()

    def test_next_question_combines_current_and_historical_rotation_context(self):
        interview = {
            "student_id": 1,
            "round_type": "technical",
            "subject": "Python",
            "difficulty": "beginner",
        }
        generated = {
            "topic_area": "modules and imports",
            "question": "What is a Python module used for?",
        }
        with self.app.app_context():
            with (
                patch.object(answers_routes, "daily_answered_count", return_value=0),
                patch.object(
                    answers_routes,
                    "recent_questions_for_student",
                    return_value=["Historical question?", "current question"],
                ),
                patch.object(
                    answers_routes,
                    "recent_topic_areas_for_student",
                    return_value=["exceptions", "collections"],
                ),
                patch.object(
                    answers_routes.groq_client,
                    "generate_question",
                    return_value=generated,
                ) as generate_question,
                patch.object(
                    answers_routes.groq_client,
                    "infer_role_skills",
                    return_value=[],
                ),
                patch.object(
                    answers_routes,
                    "get_recent_asked_history",
                    return_value=(set(), []),
                ),
                patch.object(
                    answers_routes.db, "query", return_value=(None, 1)
                ) as query,
            ):
                response = answers_routes._issue_next_question(
                    41,
                    interview,
                    2,
                    ["Current question?", "Current second?"],
                    ["collections", "functions"],
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["topic_area"], "modules and imports")
        generate_question.assert_called_once_with(
            "technical",
            "Python",
            "beginner",
            ["Current question?", "Current second?", "Historical question?"],
            ["collections", "functions", "exceptions"],
            role_context=None,
            role_skills=[],
        )
        insert_sql, insert_params = next(
            call.args[:2]
            for call in query.call_args_list
            if "INSERT INTO interview_details" in call.args[0]
        )
        self.assertIn("topic_area", insert_sql)
        self.assertEqual(
            insert_params,
            (
                41, 3, "What is a Python module used for?", "ai_generated",
                "modules and imports", "Python",
            ),
        )

    def test_submit_answer_runs_evaluation_and_returns_completion_signal(self):
        current = {
            "id": 9,
            "interview_id": 41,
            "question_order": 1,
            "question": "What is a generator?",
            "is_followup": 0,
            "answer": None,
            "verdict": None,
            "verdict_reason": None,
            "ideal_answer": None,
            "timed_out": 0,
            "processing_status": "question_ready",
        }
        interview = {
            "id": 41,
            "student_id": 1,
            "round_type": "technical",
            "subject": "Python",
            "difficulty": "beginner",
            "num_questions": 1,
            "status": "in_progress",
        }

        def query_result(sql, _params=None, fetch=False, fetchone=False):
            compact = " ".join(sql.split())
            if "question_order = %s" in compact and "ORDER BY id DESC" in compact:
                return current.copy(), 0
            if compact.startswith("SELECT * FROM interviews"):
                return interview.copy(), 0
            if "question_order > %s" in compact:
                return None, 0
            if compact.startswith("SELECT * FROM interview_details WHERE interview_id"):
                return [current.copy()], 0
            return None, 0

        evaluation = {
            "verdict": "correct",
            "reason": "You explained lazy iteration accurately.",
            "ideal_answer": "A generator yields values lazily.",
            "follow_up_needed": False,
            "follow_up_question": None,
        }
        with (
            patch("routes.answers.db.query", side_effect=query_result),
            patch(
                "routes.answers.db.save_answer_with_optional_daily_usage",
                return_value={
                    "saved": True,
                    "limit_reached": False,
                    "answered_count": 0,
                },
            ) as save_answer,
            patch("routes.answers.daily_answered_count", return_value=0),
            patch(
                "routes.answers.groq_client.evaluate_answer",
                return_value=evaluation,
            ) as evaluate_answer,
        ):
            response = self.client.post(
                "/api/submit_answer",
                json={
                    "interview_id": 41,
                    "question_order": 1,
                    "answer": "It yields values one at a time lazily.",
                    "time_taken_sec": 12,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["done"])
        self.assertIsNone(payload["verdict"])
        save_answer.assert_called_once()
        evaluate_answer.assert_not_called()

    def test_complete_interview_returns_scorecard_and_persists_scores(self):
        interview = {
            "id": 41,
            "student_id": 1,
            "round_type": "technical",
            "subject": "Python",
            "difficulty": "beginner",
            "num_questions": 1,
            "status": "in_progress",
        }
        rows = [{
            "question_order": 1,
            "question": "What is a generator?",
            "answer": "It yields values lazily.",
            "time_taken_sec": 12,
            "is_followup": 0,
            "answer_audio_path": None,
            "verdict": "correct",
            "verdict_reason": "Accurate.",
            "ideal_answer": "A generator yields lazily.",
            "timed_out": 0,
        }]
        result = {
            "overall_score": 8.5,
            "technical_accuracy": 9.0,
            "communication_clarity": 8.0,
            "confidence": 8.0,
            "strengths": json.dumps(["Accurate concepts", "Clear response"]),
            "weaknesses": json.dumps(["Add an example", "Discuss memory use"]),
            "feedback": "A strong answer with room for one concrete example.",
        }

        def query_result(sql, _params=None, fetch=False, fetchone=False):
            compact = " ".join(sql.split())
            if compact.startswith("SELECT * FROM interviews"):
                return interview.copy(), 0
            if compact.startswith("SELECT question_order"):
                return [row.copy() for row in rows], 0
            return None, 0

        with (
            patch("routes.interviews.db.query", side_effect=query_result) as query,
            patch(
                "routes.interviews.groq_client.evaluate_interview",
                return_value=result.copy(),
            ),
        ):
            response = self.client.post(
                "/api/end_interview", json={"interview_id": 41}
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["overall_score"], 8.5)
        self.assertEqual(payload["total_marks"], 1)
        self.assertTrue(any(
            "UPDATE interviews SET" in call.args[0]
            for call in query.call_args_list
        ))

    def test_exit_interview_reports_actual_transition(self):
        def query_result(sql, _params=None, fetch=False, fetchone=False):
            if "SELECT id, status FROM interviews" in sql:
                return {"id": 52, "status": "in_progress"}, 0
            if "SELECT COUNT(*) AS completed_count" in sql:
                return {"completed_count": 2}, 0
            return None, 0

        with (
            patch("routes.interviews.db.query", side_effect=query_result),
            patch("routes.interviews.db.execute_update", return_value=1) as update,
        ):
            response = self.client.post(
                "/api/exit_interview", json={"interview_id": 52}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "exited")
        self.assertEqual(response.get_json()["completed_question_count"], 2)
        update.assert_called_once()

    def test_history_is_paginated_at_the_http_boundary(self):
        history_rows = [{
            "id": 3,
            "student_name": "Integration Student",
            "student_id": 1,
            "job_role": "Data Scientist",
            "role_name": "Data Scientist",
            "subject": "Python",
            "round_type": "technical",
            "difficulty": "beginner",
            "started_at": datetime(2026, 8, 1, 10, 0),
            "ended_at": datetime(2026, 8, 1, 10, 10),
            "duration_seconds": 600,
            "total_questions": 5,
            "overall_score": 8.0,
            "status": "completed",
        }]
        with patch(
            "routes.history.db.query",
            side_effect=[({"total_items": 5}, 0), (history_rows, 0)],
        ) as query:
            response = self.client.get("/api/history/1?page=2&limit=2")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["pagination"]["page"], 2)
        self.assertEqual(payload["pagination"]["limit"], 2)
        self.assertEqual(payload["pagination"]["total_items"], 5)
        self.assertEqual(payload["items"][0]["total_questions"], 5)
        self.assertEqual(payload["items"][0]["role_name"], "Data Scientist")
        self.assertEqual(payload["items"][0]["job_role"], "Data Scientist")
        self.assertEqual(query.call_args_list[1].args[1], (1, 2, 2))

    def test_dashboard_and_profile_read_models_are_exposed(self):
        summary = {
            "total_interviews": 0,
            "average_score": None,
            "highest_score": None,
            "technical_performance": None,
            "communication_performance": None,
            "weekly_practice_count": 0,
            "interviews_this_month": 0,
            "subject_averages": None,
        }
        improvement = {
            "scored_count": 0,
            "recent_count": 0,
            "recent_average": None,
            "earlier_average": None,
        }
        with patch(
            "routes.dashboard.db.query",
            side_effect=[(summary, 0), (improvement, 0), ([], 0)],
        ):
            dashboard_response = self.client.get("/api/dashboard/1")

        profile = {
            "id": 1,
            "name": "Integration Student",
            "email": "integration@example.test",
            "phone": None,
            "course_enrolled": "Mock Interviews",
            "target_role": "Developer",
            "bio": None,
            "avatar_color": "#4dd8c8",
            "avatar_url": None,
            "total_interviews": 0,
            "average_score": None,
            "technical_interviews_count": 0,
            "hr_interviews_count": 0,
        }
        with patch("routes.profile._student_profile", return_value=profile):
            profile_response = self.client.get("/api/profile/1")

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(dashboard_response.get_json()["total_interviews"], 0)
        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(profile_response.get_json()["email"], "integration@example.test")


if __name__ == "__main__":
    unittest.main()
