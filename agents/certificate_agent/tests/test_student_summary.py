"""Phase 2 readiness skill: get_student_summary scoring."""
from datetime import datetime

from cert_app.services.readiness import build_student_summary


def test_nothing_finished_has_no_score():
    body = build_student_summary([], [])
    assert body["schema"] == "digidara.student_summary.v1" and body["score"] is None


def test_best_score_per_topic_and_certified_topics():
    exams = [
        {"topic": "Python", "score_percentage": 50, "completed_at": datetime(2026, 9, 1)},
        {"topic": "Python", "score_percentage": 85, "completed_at": datetime(2026, 9, 5)},
        {"topic": "Machine Learning", "score_percentage": 40, "completed_at": datetime(2026, 9, 3)},
    ]
    certificates = [{"topic": "Python", "score_percentage": 85, "issued_at": datetime(2026, 9, 5)}]
    body = build_student_summary(exams, certificates)
    assert body["score"] == 62.5
    assert body["strengths"] == ["Certified: Python"]
    assert body["gaps"] == ["Not certified yet: Machine Learning (best 40%)"]
    assert body["metrics"] == {"certificates": 1, "exams_finished": 3, "topics": 2}
    assert body["last_activity_at"].startswith("2026-09-05")


def test_chat_mode_certificate_without_an_exam_row_counts():
    body = build_student_summary([], [{"topic": "GenAI", "score_percentage": 90, "issued_at": None}])
    assert body["score"] == 90.0 and body["last_activity_at"] is None
