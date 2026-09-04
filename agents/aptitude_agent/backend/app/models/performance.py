from ..extensions import db
from .base import utcnow


class TopicPerformance(db.Model):
    __tablename__ = "aptitude_topic_performance"
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(128), db.ForeignKey("students.id"), nullable=False, index=True)
    category = db.Column(db.String(80), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    correct_count = db.Column(db.Integer, default=0, nullable=False)
    accuracy = db.Column(db.Numeric(5, 2), default=0, nullable=False)
    average_time_seconds = db.Column(db.Numeric(7, 2), default=0, nullable=False)
    last_updated = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("student_id", "category", "topic", name="uq_student_category_topic"),)

