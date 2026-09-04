from ..extensions import db
from .base import utcnow


class LearnerLastTopics(db.Model):
    """Latest successful topic schedule stored per learner/category/scope.

    New Mixed and Category Practice attempts share the ``Shared`` scope. Older
    level-specific rows remain readable for migration-free compatibility.
    """

    __tablename__ = "learner_last_topics"
    id = db.Column(db.String(36), primary_key=True)
    learner_id = db.Column(db.String(128), db.ForeignKey("students.id"), nullable=False, index=True)
    category_id = db.Column(db.String(80), nullable=False)
    level = db.Column(db.String(20), nullable=False)
    topics_used = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("learner_id", "category_id", "level", name="uq_learner_last_topics_scope"),
    )
