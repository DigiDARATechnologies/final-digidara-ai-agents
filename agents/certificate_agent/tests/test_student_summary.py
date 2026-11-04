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
    assert body["resume"]["certifications"] == [
        {"name": "Python Certification", "issuer": "SkillDARA AI Certification", "date": "2026-09-05", "score": 85}]


def test_chat_mode_certificate_without_an_exam_row_counts():
    body = build_student_summary([], [{"topic": "GenAI", "score_percentage": 90, "issued_at": None}])
    assert body["score"] == 90.0 and body["last_activity_at"] is None


def test_each_exam_counts_at_every_level_it_asked_and_never_lowers_progress():
    exams = [{"id": n, "topic": "Python", "score_percentage": 70, "completed_at": datetime(2026, 9, n)} for n in (1, 2)]
    answers = [
        {"exam_id": 1, "difficulty": "beginner", "correct": 9, "asked": 10},      # 90%: a pass, counts in full
        {"exam_id": 1, "difficulty": "intermediate", "correct": 6, "asked": 10},  # 60%: counts 75
        {"exam_id": 1, "difficulty": "advanced", "correct": 2, "asked": 2},       # too few questions to count
        {"exam_id": 2, "difficulty": "beginner", "correct": 2, "asked": 10},      # a weak exam adds a little
        {"exam_id": 9, "difficulty": "beginner", "correct": 10, "asked": 10},     # not a finished exam
    ]
    body = build_student_summary(exams, [], answers)
    assert body["level_scores"] == {"easy": 25.0, "medium": 15.0, "hard": 0.0, "professional": 0.0}


def test_five_passed_exams_complete_a_level():
    exams = [{"id": n, "topic": "SQL", "score_percentage": 85, "completed_at": datetime(2026, 9, n)} for n in range(1, 7)]
    answers = [{"exam_id": n, "difficulty": "beginner", "correct": 8, "asked": 10} for n in range(1, 6)]
    answers.append({"exam_id": 6, "difficulty": "beginner", "correct": 1, "asked": 10})
    assert build_student_summary(exams, [], answers)["level_scores"]["easy"] == 100.0


def test_professional_needs_90_percent_of_the_advanced_answers():
    exams = [{"id": n, "topic": "SQL", "score_percentage": 85, "completed_at": datetime(2026, 9, n)} for n in range(1, 6)]
    at_80 = [{"exam_id": n, "difficulty": "advanced", "correct": 8, "asked": 10} for n in range(1, 6)]
    scores = build_student_summary(exams, [], at_80)["level_scores"]
    assert scores["hard"] == 100.0 and scores["professional"] == 88.9
    at_90 = [{**row, "correct": 9} for row in at_80]
    assert build_student_summary(exams, [], at_90)["level_scores"]["professional"] == 100.0


def test_without_answers_no_level_scores_are_sent():
    body = build_student_summary([], [{"topic": "GenAI", "score_percentage": 90, "issued_at": None}])
    assert "level_scores" not in body


def test_level_goals_count_exams_at_the_pass_mark():
    from cert_app.services.readiness import level_goals
    answers = [{"exam_id": i, "difficulty": "advanced", "correct": c, "asked": 10} for i, c in enumerate((9, 8, 7))]
    goals = level_goals(answers)
    assert goals["hard"] == {"needed": 5, "done": 2, "pass_percent": 80, "unit": "exam"}
    assert goals["professional"]["done"] == 1 and goals["easy"]["done"] == 0
