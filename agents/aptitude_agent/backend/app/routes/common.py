from datetime import datetime, timezone
from flask import g
from ..models import AptitudeTest
from ..models.base import utc_isoformat
from ..services.adaptive_service import difficulty_metrics
from ..services.test_label import test_label
from ..topic_config import topic_is_starred
from ..utils.errors import APIError


def utcnow(): return datetime.now(timezone.utc)


def owned_test(test_id):
    test=AptitudeTest.query.filter_by(id=test_id,student_id=g.student.id).first()
    if not test: raise APIError("Assessment not found",404,"test_not_found")
    return test


def elapsed_seconds(question):
    if not question.question_started_at:return 0
    started=question.question_started_at
    if started.tzinfo is None:started=started.replace(tzinfo=timezone.utc)
    return max(0,int((utcnow()-started).total_seconds()))


def test_duration_seconds(test):
    """Return completed-test wall-clock duration without timezone ambiguity."""
    if not test.started_at or not test.completed_at:
        return test.total_time_seconds
    started=test.started_at if test.started_at.tzinfo else test.started_at.replace(tzinfo=timezone.utc)
    completed=test.completed_at if test.completed_at.tzinfo else test.completed_at.replace(tzinfo=timezone.utc)
    return max(0,int((completed.astimezone(timezone.utc)-started.astimezone(timezone.utc)).total_seconds()))


def public_question(question,test):
    display_difficulty=test.selected_level if test.test_mode=="category_practice" else question.difficulty
    return {"id":question.id,"sequence":question.sequence_no,"total":test.total_questions,"test_mode":test.test_mode,"selected_category":test.selected_category,"selected_level":test.selected_level,"technical_language":test.technical_language,"category":question.category,"topic":question.topic,"topic_is_starred":topic_is_starred(question.category,question.topic),"difficulty":question.difficulty,"display_difficulty":display_difficulty,"question":question.question_text,"options":question.options,"allowed_seconds":question.allowed_time_seconds,"remaining_seconds":max(0,question.allowed_time_seconds-elapsed_seconds(question)),"hint":question.hint_text if question.hint_requested else None,"hint_requested":bool(question.hint_requested),"hints_remaining":max(0,test.hints_allowed-test.hints_used)}


def test_summary(test):
    difficulty=difficulty_metrics(test)
    answers=[question.answer for question in test.questions if question.answer]
    occurred_at=test.completed_at or test.last_activity_at or test.started_at
    return {"id":test.id,"name":test_label(test),"status":test.status,"test_mode":test.test_mode,"selected_category":test.selected_category,"selected_level":test.selected_level,"technical_language":test.technical_language,"date":utc_isoformat(occurred_at),"score":test.score,"total":test.total_questions,"answered_count":len(answers),"percentage":float(test.percentage),"correct":test.correct_count,"wrong":test.wrong_count,"timed_out":test.timed_out_count,"hints_used":test.hints_used,"hints_allowed":test.hints_allowed,"hints_remaining":max(0,test.hints_allowed-test.hints_used),"total_time":test.total_time_seconds,"duration_seconds":test_duration_seconds(test),"average_time":round(test.total_time_seconds/test.total_questions,1) if test.total_questions else 0,**difficulty}
