from ..extensions import db
from .base import utcnow


class AptitudeTestQuestion(db.Model):
    __tablename__ = "aptitude_test_questions"
    id = db.Column(db.String(36), primary_key=True)
    test_id = db.Column(db.String(36), db.ForeignKey("aptitude_tests.id"), nullable=False, index=True)
    sequence_no = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.Enum("Easy", "Medium", "Hard", name="question_difficulty"), nullable=False)
    difficulty_reason = db.Column(db.String(255))
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500), nullable=False)
    option_b = db.Column(db.String(500), nullable=False)
    option_c = db.Column(db.String(500), nullable=False)
    option_d = db.Column(db.String(500), nullable=False)
    correct_answer = db.Column(db.Enum("A", "B", "C", "D", name="answer_option"), nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    allowed_time_seconds = db.Column(db.Integer, default=60, nullable=False)
    question_started_at = db.Column(db.DateTime(timezone=True))
    time_spent_seconds = db.Column(db.Integer, default=0, nullable=False)
    visited = db.Column(db.Boolean, default=False, nullable=False)
    hint_text = db.Column(db.Text)
    hint_requested = db.Column(db.Boolean, default=False, nullable=False)
    hint_requested_at = db.Column(db.DateTime(timezone=True))
    generation_model = db.Column(db.String(100))
    prompt_version = db.Column(db.String(30), default="v1", nullable=False)
    validation_status = db.Column(db.String(30), default="accepted", nullable=False)
    regeneration_count = db.Column(db.Integer, default=0, nullable=False)
    content_hash = db.Column(db.String(64), nullable=False, index=True)
    structural_hash = db.Column(db.String(64), index=True)
    source_bank_item_id = db.Column(db.String(36), db.ForeignKey("aptitude_question_bank.id"), index=True)
    generated_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    answer = db.relationship("AptitudeAnswer", backref="question", uselist=False, cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("test_id", "sequence_no", name="uq_test_sequence"),)

    @property
    def options(self):
        return {"A": self.option_a, "B": self.option_b, "C": self.option_c, "D": self.option_d}
