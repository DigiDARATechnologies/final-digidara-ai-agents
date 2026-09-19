from ..extensions import db
from .base import utcnow


class AptitudeTest(db.Model):
    __tablename__ = "aptitude_tests"
    id = db.Column(db.String(36), primary_key=True)
    student_id = db.Column(db.String(128), db.ForeignKey("students.id"), nullable=False, index=True)
    status = db.Column(db.Enum("generating", "ready", "in_progress", "completed", "abandoned", "failed", name="test_status"), nullable=False, default="generating", index=True)
    current_sequence = db.Column(db.Integer, default=1, nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    assessment_started_at = db.Column(db.DateTime(timezone=True))
    total_duration_seconds = db.Column(db.Integer)
    expires_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    last_activity_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    total_questions = db.Column(db.Integer, default=20, nullable=False)
    test_mode = db.Column(db.Enum("mixed", "category_practice", name="test_mode"), default="mixed", nullable=False, index=True)
    selected_category = db.Column(db.String(80))
    selected_level = db.Column(db.Enum("Beginner", "Intermediate", "Advanced", name="practice_level"))
    technical_language = db.Column(db.String(20))
    timezone = db.Column(db.String(80))
    focus_category = db.Column(db.String(80))
    # Immutable per-attempt snapshot of the learner's six configured counts.
    mixed_category_counts = db.Column(db.JSON)
    hints_used = db.Column(db.Integer, default=0, nullable=False)
    hints_allowed = db.Column(db.Integer, default=3, nullable=False)
    correct_count = db.Column(db.Integer, default=0, nullable=False)
    wrong_count = db.Column(db.Integer, default=0, nullable=False)
    timed_out_count = db.Column(db.Integer, default=0, nullable=False)
    score = db.Column(db.Integer, default=0, nullable=False)
    percentage = db.Column(db.Numeric(5, 2), default=0, nullable=False)
    total_time_seconds = db.Column(db.Integer, default=0, nullable=False)
    questions = db.relationship("AptitudeTestQuestion", backref="test", cascade="all, delete-orphan", order_by="AptitudeTestQuestion.sequence_no")
