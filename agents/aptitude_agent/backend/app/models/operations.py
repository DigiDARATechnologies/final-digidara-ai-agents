from ..extensions import db
from .base import utcnow


class RecentQuestionHash(db.Model):
    __tablename__ = "aptitude_recent_question_hashes"
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(128), db.ForeignKey("students.id"), nullable=False)
    test_id = db.Column(db.String(36), db.ForeignKey("aptitude_tests.id"), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    structural_hash = db.Column(db.String(64))
    bank_question_id = db.Column(db.String(36), db.ForeignKey("aptitude_question_bank.id"), index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (db.Index("ix_recent_hash_student", "student_id"), db.Index("ix_recent_hash_content", "content_hash"), db.Index("ix_recent_hash_structural", "structural_hash"))


class AIRecommendation(db.Model):
    __tablename__ = "aptitude_ai_recommendations"
    id = db.Column(db.String(36), primary_key=True)
    test_id = db.Column(db.String(36), db.ForeignKey("aptitude_tests.id"), nullable=False, unique=True)
    student_id = db.Column(db.String(128), db.ForeignKey("students.id"), nullable=False)
    status = db.Column(db.Enum("pending", "processing", "completed", "failed", name="recommendation_status"), default="pending", nullable=False)
    recommendation_text = db.Column(db.Text)
    model_version = db.Column(db.String(100))
    attempt_count = db.Column(db.Integer, default=0, nullable=False)
    last_error = db.Column(db.String(500))
    generated_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (db.Index("ix_recommendation_student", "student_id"),)


class BackgroundJob(db.Model):
    __tablename__ = "aptitude_background_jobs"
    id = db.Column(db.String(36), primary_key=True)
    job_type = db.Column(db.String(50), nullable=False)
    test_id = db.Column(db.String(36), db.ForeignKey("aptitude_tests.id"))
    student_id = db.Column(db.String(128), db.ForeignKey("students.id"))
    status = db.Column(db.Enum("pending", "processing", "completed", "failed", name="job_status"), default="pending", nullable=False)
    payload_json = db.Column(db.JSON, nullable=False)
    dedupe_key = db.Column(db.String(190), unique=True)
    attempt_count = db.Column(db.Integer, default=0, nullable=False)
    max_attempts = db.Column(db.Integer, default=3, nullable=False)
    available_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    locked_at = db.Column(db.DateTime(timezone=True))
    locked_by = db.Column(db.String(180))
    last_error = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True))
    __table_args__ = (db.Index("ix_jobs_status_available", "status", "available_at"), db.Index("ix_jobs_test", "test_id"), db.Index("ix_jobs_student", "student_id"))


class WorkerHeartbeat(db.Model):
    __tablename__ = "aptitude_worker_heartbeats"
    worker_id = db.Column(db.String(180), primary_key=True)
    hostname = db.Column(db.String(180), nullable=False)
    process_id = db.Column(db.Integer, nullable=False)
    status = db.Column(db.Enum("starting", "idle", "working", "stopping", "stopped", "dead", name="worker_status"), default="starting", nullable=False)
    current_job_id = db.Column(db.String(36))
    started_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    heartbeat_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class BankGenerationLease(db.Model):
    """One MySQL-backed lease prevents parallel workers bursting OpenAI."""
    __tablename__ = "aptitude_bank_generation_leases"
    name = db.Column(db.String(80), primary_key=True)
    locked_by = db.Column(db.String(180))
    locked_until = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class QuestionBankItem(db.Model):
    __tablename__ = "aptitude_question_bank"
    id = db.Column(db.String(36), primary_key=True)
    category = db.Column(db.String(80), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    difficulty = db.Column(db.Enum("Easy", "Medium", "Hard", name="bank_question_difficulty"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500), nullable=False)
    option_b = db.Column(db.String(500), nullable=False)
    option_c = db.Column(db.String(500), nullable=False)
    option_d = db.Column(db.String(500), nullable=False)
    correct_answer = db.Column(db.Enum("A", "B", "C", "D", name="bank_answer_option"), nullable=False)
    explanation = db.Column(db.Text, nullable=False)
    hint_text = db.Column(db.Text)
    content_hash = db.Column(db.String(64), nullable=False, unique=True)
    structural_hash = db.Column(db.String(64), index=True)
    status = db.Column(db.Enum("draft", "review", "approved", "retired", "archived", name="bank_item_status"), default="draft", nullable=False)
    version = db.Column(db.Integer, default=1, nullable=False)
    source_model = db.Column(db.String(100))
    prompt_version = db.Column(db.String(30), default="bank-v1", nullable=False)
    times_used = db.Column(db.Integer, default=0, nullable=False)
    attempt_count = db.Column(db.Integer, default=0, nullable=False)
    correct_count = db.Column(db.Integer, default=0, nullable=False)
    total_time_seconds = db.Column(db.BigInteger, default=0, nullable=False)
    option_counts_json = db.Column(db.JSON, default=dict, nullable=False)
    report_count = db.Column(db.Integer, default=0, nullable=False)
    approved_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    __table_args__ = (
        db.Index("ix_bank_selection", "status", "category", "topic", "difficulty", "times_used"),
        db.Index("ix_bank_category_difficulty", "category", "difficulty"),
    )

    @property
    def options(self):
        return {"A": self.option_a, "B": self.option_b, "C": self.option_c, "D": self.option_d}

    @property
    def observed_accuracy(self):
        return round(self.correct_count/self.attempt_count*100,2) if self.attempt_count else None


class AuditEvent(db.Model):
    __tablename__ = "aptitude_audit_events"
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(128), db.ForeignKey("students.id"))
    test_id = db.Column(db.String(36), db.ForeignKey("aptitude_tests.id"))
    event_type = db.Column(db.String(60), nullable=False)
    request_id = db.Column(db.String(80))
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (db.Index("ix_audit_student", "student_id"), db.Index("ix_audit_test", "test_id"), db.Index("ix_audit_type", "event_type"), db.Index("ix_audit_request", "request_id"), db.Index("ix_audit_created", "created_at"))


class RateLimitEvent(db.Model):
    __tablename__ = "aptitude_rate_limit_events"
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    student_id = db.Column(db.String(128), db.ForeignKey("students.id"), nullable=False)
    action = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (db.Index("ix_rate_student_action_created", "student_id", "action", "created_at"),)


class AIUsageEvent(db.Model):
    __tablename__ = "aptitude_ai_usage_events"
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    # System jobs (for example question-bank replenishment) have no learner.
    student_id = db.Column(db.String(128), db.ForeignKey("students.id"), nullable=True)
    test_id = db.Column(db.String(36), db.ForeignKey("aptitude_tests.id"))
    question_id = db.Column(db.String(36), db.ForeignKey("aptitude_test_questions.id"))
    operation = db.Column(db.String(40), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    input_tokens = db.Column(db.Integer, default=0, nullable=False)
    output_tokens = db.Column(db.Integer, default=0, nullable=False)
    total_tokens = db.Column(db.Integer, default=0, nullable=False)
    estimated_cost_usd = db.Column(db.Numeric(14, 8), default=0, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    __table_args__ = (
        db.Index("ix_ai_usage_student_created", "student_id", "created_at"),
        db.Index("ix_ai_usage_test", "test_id"),
        db.Index("ix_ai_usage_question", "question_id"),
    )
