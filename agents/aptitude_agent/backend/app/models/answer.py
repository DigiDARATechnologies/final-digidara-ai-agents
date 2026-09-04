from ..extensions import db
from .base import utcnow


class AptitudeAnswer(db.Model):
    __tablename__ = "aptitude_answers"
    id = db.Column(db.String(36), primary_key=True)
    test_id = db.Column(db.String(36), db.ForeignKey("aptitude_tests.id"), nullable=False, index=True)
    student_id = db.Column(db.String(128), db.ForeignKey("students.id"), nullable=False, index=True)
    question_id = db.Column(db.String(36), db.ForeignKey("aptitude_test_questions.id"), nullable=False, unique=True)
    selected_answer = db.Column(db.Enum("A", "B", "C", "D", name="selected_option"))
    correct_answer = db.Column(db.Enum("A", "B", "C", "D", name="stored_answer_option"), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    timed_out = db.Column(db.Boolean, default=False, nullable=False)
    confidence_rating = db.Column(db.Integer)
    mistake_type = db.Column(db.Enum("careless_slip", "conceptual_gap", "time_pressure", "not_applicable", name="mistake_type"))
    mistake_explanation = db.Column(db.Text)
    time_taken_seconds = db.Column(db.Integer, nullable=False)
    evaluation_source = db.Column(db.Enum("groq", "fallback", "fallback_consistency", "authoritative", "timeout", name="evaluation_source"), nullable=False)
    reasoning_text = db.Column(db.Text)
    reasoning_quality = db.Column(db.Enum("strong", "partial", "weak", "none", name="reasoning_quality"))
    reasoning_verdict = db.Column(db.Enum("correct", "incorrect", "partially_correct", name="reasoning_verdict"))
    reasoning_confidence = db.Column(db.Float)
    reasoning_feedback = db.Column(db.Text)
    diagnostics_error = db.Column(db.Text)
    outcome_type = db.Column(db.Enum("correct_sound_reasoning", "correct_flawed_reasoning", "incorrect_close_reasoning", "incorrect_flawed_reasoning", "no_reasoning_given", name="answer_outcome_type"))
    diagnostics_status = db.Column(db.Enum("not_requested", "pending", "completed", "unavailable", "failed", name="diagnostics_status"), default="not_requested", nullable=False)
    answered_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
