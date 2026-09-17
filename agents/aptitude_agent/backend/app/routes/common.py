from datetime import datetime, timezone
from flask import g
from ..models import AptitudeTest
from ..models.base import utc_isoformat
from ..services.test_question_service import difficulty_metrics
from ..services.test_label import test_label
from ..topic_config import topic_is_starred
from ..utils.errors import APIError

DIFFICULTY_TIME_SECONDS={"easy":60,"beginner":60,"medium":90,"intermediate":90,"hard":120,"advanced":120}


def utcnow(): return datetime.now(timezone.utc)


def owned_test(test_id):
    test=AptitudeTest.query.filter_by(id=test_id,student_id=g.student.id).first()
    if not test: raise APIError("Assessment not found",404,"test_not_found")
    return test


def elapsed_seconds(question):
    spent=int(getattr(question,"time_spent_seconds",0) or 0)
    if not question.question_started_at:return spent
    started=question.question_started_at
    if started.tzinfo is None:started=started.replace(tzinfo=timezone.utc)
    return spent+max(0,int((utcnow()-started).total_seconds()))


def pause_question(question):
    """Persist elapsed time and stop this question's clock while navigating."""
    if question.question_started_at:
        question.time_spent_seconds=elapsed_seconds(question)
        question.question_started_at=None


def start_question(question):
    if not question.question_started_at:
        question.question_started_at=utcnow()
    question.visited=True


def difficulty_seconds(difficulty):
    value=str(difficulty or "").strip().casefold()
    if value not in DIFFICULTY_TIME_SECONDS:
        raise APIError(f"Unsupported question difficulty: {difficulty}",500,"invalid_question_difficulty")
    return DIFFICULTY_TIME_SECONDS[value]


def calculate_test_duration(test):
    return sum(difficulty_seconds(question.difficulty) for question in test.questions)


def overall_remaining_seconds(test):
    if not test.expires_at:
        return int(test.total_duration_seconds or 0)
    expires=test.expires_at if test.expires_at.tzinfo else test.expires_at.replace(tzinfo=timezone.utc)
    return max(0,int((expires.astimezone(timezone.utc)-utcnow()).total_seconds()))


def ensure_overall_timer(test):
    if not test.total_duration_seconds:
        test.total_duration_seconds=calculate_test_duration(test)
    if not test.assessment_started_at:
        test.assessment_started_at=utcnow()
    if not test.expires_at:
        from datetime import timedelta
        test.expires_at=test.assessment_started_at+timedelta(seconds=test.total_duration_seconds)
    return overall_remaining_seconds(test)


def test_duration_seconds(test):
    """Return completed-test wall-clock duration without timezone ambiguity."""
    if not test.started_at or not test.completed_at:
        return test.total_time_seconds
    started=test.started_at if test.started_at.tzinfo else test.started_at.replace(tzinfo=timezone.utc)
    completed=test.completed_at if test.completed_at.tzinfo else test.completed_at.replace(tzinfo=timezone.utc)
    return max(0,int((completed.astimezone(timezone.utc)-started.astimezone(timezone.utc)).total_seconds()))


def public_question(question,test):
    display_difficulty=test.selected_level if test.test_mode=="category_practice" else question.difficulty
    answer=question.answer
    timed_out=bool(answer and answer.timed_out)
    navigation=[{"sequence":item.sequence_no,"status":"timed_out" if item.answer and item.answer.timed_out else "answered" if item.answer else "unanswered","visited":bool(item.visited)} for item in test.questions]
    remaining=overall_remaining_seconds(test)
    expires_at=test.expires_at
    if expires_at and expires_at.tzinfo is None: expires_at=expires_at.replace(tzinfo=timezone.utc)
    return {"id":question.id,"sequence":question.sequence_no,"total":test.total_questions,"test_id":test.id,"test_mode":test.test_mode,"selected_category":test.selected_category,"selected_level":test.selected_level,"technical_language":test.technical_language,"category":question.category,"topic":question.topic,"topic_is_starred":topic_is_starred(question.category,question.topic),"difficulty":question.difficulty,"display_difficulty":display_difficulty,"question":question.question_text,"options":question.options,"allowed_seconds":question.allowed_time_seconds,"remaining_seconds":remaining,"overall_remaining_seconds":remaining,"total_duration_seconds":test.total_duration_seconds,"expires_at":expires_at.isoformat() if expires_at else None,"hint":question.hint_text if question.hint_requested else None,"hint_requested":bool(question.hint_requested),"hints_remaining":max(0,test.hints_allowed-test.hints_used),"answered":bool(answer and not timed_out),"timed_out":timed_out,"visited":bool(question.visited),"status":"timed_out" if timed_out else "answered" if answer else "unanswered","navigation":navigation}


def test_summary(test):
    difficulty=difficulty_metrics(test)
    answers=[question.answer for question in test.questions if question.answer]
    occurred_at=test.completed_at or test.last_activity_at or test.started_at
    return {"id":test.id,"name":test_label(test),"status":test.status,"test_mode":test.test_mode,"selected_category":test.selected_category,"selected_level":test.selected_level,"technical_language":test.technical_language,"date":utc_isoformat(occurred_at),"score":test.score,"total":test.total_questions,"answered_count":len(answers),"percentage":float(test.percentage),"correct":test.correct_count,"wrong":test.wrong_count,"timed_out":test.timed_out_count,"hints_used":test.hints_used,"hints_allowed":test.hints_allowed,"hints_remaining":max(0,test.hints_allowed-test.hints_used),"total_time":test.total_time_seconds,"duration_seconds":test_duration_seconds(test),"average_time":round(test.total_time_seconds/test.total_questions,1) if test.total_questions else 0,**difficulty}
