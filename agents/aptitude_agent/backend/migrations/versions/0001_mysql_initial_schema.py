"""MySQL-only initial schema.

Revision ID: 0001_mysql_initial
Revises: None
"""
from alembic import op
import sqlalchemy as sa

revision="0001_mysql_initial"
down_revision=None
branch_labels=None
depends_on=None

test_status=sa.Enum("generating","ready","in_progress","completed","abandoned","failed",name="test_status")
difficulty=sa.Enum("Easy","Medium","Hard",name="question_difficulty")
answer_option=sa.Enum("A","B","C","D",name="answer_option")
selected_option=sa.Enum("A","B","C","D",name="selected_option")
stored_option=sa.Enum("A","B","C","D",name="stored_answer_option")
evaluation_source=sa.Enum("groq","fallback","fallback_consistency","timeout",name="evaluation_source")
recommendation_status=sa.Enum("pending","processing","completed","failed",name="recommendation_status")
job_status=sa.Enum("pending","processing","completed","failed",name="job_status")

def upgrade():
    op.create_table("students",
      sa.Column("id",sa.String(128),primary_key=True),sa.Column("name",sa.String(160),nullable=False),sa.Column("email",sa.String(255)),sa.Column("course",sa.String(160)),sa.Column("department",sa.String(160)),sa.Column("year",sa.String(40)),sa.Column("institution",sa.String(200)),sa.Column("batch",sa.String(80)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("aptitude_tests",
      sa.Column("id",sa.String(36),primary_key=True),sa.Column("student_id",sa.String(128),sa.ForeignKey("students.id"),nullable=False),sa.Column("status",test_status,nullable=False),sa.Column("current_sequence",sa.Integer,nullable=False),sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),sa.Column("completed_at",sa.DateTime(timezone=True)),sa.Column("last_activity_at",sa.DateTime(timezone=True),nullable=False),sa.Column("total_questions",sa.Integer,nullable=False),sa.Column("correct_count",sa.Integer,nullable=False),sa.Column("wrong_count",sa.Integer,nullable=False),sa.Column("timed_out_count",sa.Integer,nullable=False),sa.Column("score",sa.Integer,nullable=False),sa.Column("percentage",sa.Numeric(5,2),nullable=False),sa.Column("total_time_seconds",sa.Integer,nullable=False))
    op.create_index("ix_aptitude_tests_student_id","aptitude_tests",["student_id"]);op.create_index("ix_aptitude_tests_status","aptitude_tests",["status"])
    op.create_table("aptitude_test_questions",
      sa.Column("id",sa.String(36),primary_key=True),sa.Column("test_id",sa.String(36),sa.ForeignKey("aptitude_tests.id"),nullable=False),sa.Column("sequence_no",sa.Integer,nullable=False),sa.Column("category",sa.String(80),nullable=False),sa.Column("topic",sa.String(100),nullable=False),sa.Column("difficulty",difficulty,nullable=False),sa.Column("question_text",sa.Text,nullable=False),sa.Column("option_a",sa.String(500),nullable=False),sa.Column("option_b",sa.String(500),nullable=False),sa.Column("option_c",sa.String(500),nullable=False),sa.Column("option_d",sa.String(500),nullable=False),sa.Column("correct_answer",answer_option,nullable=False),sa.Column("explanation",sa.Text,nullable=False),sa.Column("allowed_time_seconds",sa.Integer,nullable=False),sa.Column("question_started_at",sa.DateTime(timezone=True)),sa.Column("generation_model",sa.String(100)),sa.Column("prompt_version",sa.String(30),nullable=False),sa.Column("validation_status",sa.String(30),nullable=False),sa.Column("regeneration_count",sa.Integer,nullable=False),sa.Column("content_hash",sa.String(64),nullable=False),sa.Column("generated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("test_id","sequence_no",name="uq_test_sequence"))
    op.create_index("ix_aptitude_test_questions_test_id","aptitude_test_questions",["test_id"]);op.create_index("ix_aptitude_test_questions_content_hash","aptitude_test_questions",["content_hash"])
    op.create_table("aptitude_answers",
      sa.Column("id",sa.String(36),primary_key=True),sa.Column("test_id",sa.String(36),sa.ForeignKey("aptitude_tests.id"),nullable=False),sa.Column("student_id",sa.String(128),sa.ForeignKey("students.id"),nullable=False),sa.Column("question_id",sa.String(36),sa.ForeignKey("aptitude_test_questions.id"),nullable=False,unique=True),sa.Column("selected_answer",selected_option),sa.Column("correct_answer",stored_option,nullable=False),sa.Column("is_correct",sa.Boolean,nullable=False),sa.Column("timed_out",sa.Boolean,nullable=False),sa.Column("time_taken_seconds",sa.Integer,nullable=False),sa.Column("evaluation_source",evaluation_source,nullable=False),sa.Column("answered_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_aptitude_answers_test_id","aptitude_answers",["test_id"]);op.create_index("ix_aptitude_answers_student_id","aptitude_answers",["student_id"])
    op.create_table("aptitude_topic_performance",
      sa.Column("id",sa.BigInteger,primary_key=True,autoincrement=True),sa.Column("student_id",sa.String(128),sa.ForeignKey("students.id"),nullable=False),sa.Column("category",sa.String(80),nullable=False),sa.Column("topic",sa.String(100),nullable=False),sa.Column("attempts",sa.Integer,nullable=False),sa.Column("correct_count",sa.Integer,nullable=False),sa.Column("accuracy",sa.Numeric(5,2),nullable=False),sa.Column("average_time_seconds",sa.Numeric(7,2),nullable=False),sa.Column("last_updated",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("student_id","category","topic",name="uq_student_category_topic"))
    op.create_index("ix_aptitude_topic_performance_student_id","aptitude_topic_performance",["student_id"])
    op.create_table("aptitude_recent_question_hashes",
      sa.Column("id",sa.BigInteger,primary_key=True,autoincrement=True),sa.Column("student_id",sa.String(128),sa.ForeignKey("students.id"),nullable=False),sa.Column("test_id",sa.String(36),sa.ForeignKey("aptitude_tests.id"),nullable=False),sa.Column("category",sa.String(80),nullable=False),sa.Column("topic",sa.String(100),nullable=False),sa.Column("content_hash",sa.String(64),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_recent_hash_student","aptitude_recent_question_hashes",["student_id"]);op.create_index("ix_recent_hash_content","aptitude_recent_question_hashes",["content_hash"])
    op.create_table("aptitude_ai_recommendations",
      sa.Column("id",sa.String(36),primary_key=True),sa.Column("test_id",sa.String(36),sa.ForeignKey("aptitude_tests.id"),nullable=False,unique=True),sa.Column("student_id",sa.String(128),sa.ForeignKey("students.id"),nullable=False),sa.Column("status",recommendation_status,nullable=False),sa.Column("recommendation_text",sa.Text),sa.Column("model_version",sa.String(100)),sa.Column("attempt_count",sa.Integer,nullable=False),sa.Column("last_error",sa.String(500)),sa.Column("generated_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_recommendation_student","aptitude_ai_recommendations",["student_id"])
    op.create_table("aptitude_background_jobs",
      sa.Column("id",sa.String(36),primary_key=True),sa.Column("job_type",sa.String(50),nullable=False),sa.Column("test_id",sa.String(36),sa.ForeignKey("aptitude_tests.id")),sa.Column("student_id",sa.String(128),sa.ForeignKey("students.id")),sa.Column("status",job_status,nullable=False),sa.Column("payload_json",sa.JSON,nullable=False),sa.Column("attempt_count",sa.Integer,nullable=False),sa.Column("max_attempts",sa.Integer,nullable=False),sa.Column("available_at",sa.DateTime(timezone=True),nullable=False),sa.Column("locked_at",sa.DateTime(timezone=True)),sa.Column("locked_by",sa.String(180)),sa.Column("last_error",sa.String(500)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("completed_at",sa.DateTime(timezone=True)))
    op.create_index("ix_jobs_status_available","aptitude_background_jobs",["status","available_at"]);op.create_index("ix_jobs_test","aptitude_background_jobs",["test_id"]);op.create_index("ix_jobs_student","aptitude_background_jobs",["student_id"])
    op.create_table("aptitude_audit_events",
      sa.Column("id",sa.BigInteger,primary_key=True,autoincrement=True),sa.Column("student_id",sa.String(128),sa.ForeignKey("students.id")),sa.Column("test_id",sa.String(36),sa.ForeignKey("aptitude_tests.id")),sa.Column("event_type",sa.String(60),nullable=False),sa.Column("request_id",sa.String(80)),sa.Column("metadata_json",sa.JSON,nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_audit_student","aptitude_audit_events",["student_id"]);op.create_index("ix_audit_test","aptitude_audit_events",["test_id"]);op.create_index("ix_audit_type","aptitude_audit_events",["event_type"]);op.create_index("ix_audit_request","aptitude_audit_events",["request_id"]);op.create_index("ix_audit_created","aptitude_audit_events",["created_at"])
    op.create_table("aptitude_rate_limit_events",
      sa.Column("id",sa.BigInteger,primary_key=True,autoincrement=True),sa.Column("student_id",sa.String(128),sa.ForeignKey("students.id"),nullable=False),sa.Column("action",sa.String(60),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_rate_student_action_created","aptitude_rate_limit_events",["student_id","action","created_at"])

def downgrade():
    for table in ["aptitude_rate_limit_events","aptitude_audit_events","aptitude_background_jobs","aptitude_ai_recommendations","aptitude_recent_question_hashes","aptitude_topic_performance","aptitude_answers","aptitude_test_questions","aptitude_tests","students"]:op.drop_table(table)
