from ..extensions import db
from .base import utcnow


class LearnerMixedTestConfig(db.Model):
    """One independently editable Mixed Test category count per learner."""

    __tablename__ = "learner_mixed_test_config"

    id = db.Column(db.String(36), primary_key=True)
    learner_id = db.Column(
        db.String(128), db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    category_id = db.Column(db.String(50), nullable=False)
    category_name = db.Column(db.String(80), nullable=False)
    question_count = db.Column(db.Integer, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow,
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "learner_id", "category_id", name="uq_learner_mixed_test_category",
        ),
        db.CheckConstraint(
            "question_count >= 3 AND question_count <= 10",
            name="ck_learner_mixed_question_count",
        ),
    )
