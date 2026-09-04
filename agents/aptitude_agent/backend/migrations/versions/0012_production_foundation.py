"""Add question bank, asynchronous diagnostics, and worker operations.

Revision ID: 0012_production_foundation
Revises: 0011_remove_weighted_scoring
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_production_foundation"
down_revision = "0011_remove_weighted_scoring"
branch_labels = None
depends_on = None


def upgrade():
    diagnostics_status=sa.Enum("not_requested","pending","completed","failed",name="diagnostics_status")
    worker_status=sa.Enum("starting","idle","working","stopping",name="worker_status")
    bank_difficulty=sa.Enum("Easy","Medium","Hard",name="bank_question_difficulty")
    bank_answer=sa.Enum("A","B","C","D",name="bank_answer_option")
    bank_status=sa.Enum("draft","review","approved","retired",name="bank_item_status")
    op.create_table(
        "aptitude_question_bank",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("category",sa.String(80),nullable=False),sa.Column("topic",sa.String(100),nullable=False),
        sa.Column("difficulty",bank_difficulty,nullable=False),sa.Column("question_text",sa.Text,nullable=False),
        sa.Column("option_a",sa.String(500),nullable=False),sa.Column("option_b",sa.String(500),nullable=False),
        sa.Column("option_c",sa.String(500),nullable=False),sa.Column("option_d",sa.String(500),nullable=False),
        sa.Column("correct_answer",bank_answer,nullable=False),sa.Column("explanation",sa.Text,nullable=False),
        sa.Column("content_hash",sa.String(64),nullable=False,unique=True),sa.Column("status",bank_status,nullable=False),
        sa.Column("version",sa.Integer,nullable=False),sa.Column("source_model",sa.String(100)),
        sa.Column("prompt_version",sa.String(30),nullable=False),sa.Column("times_used",sa.Integer,nullable=False),
        sa.Column("attempt_count",sa.Integer,nullable=False),sa.Column("correct_count",sa.Integer,nullable=False),
        sa.Column("total_time_seconds",sa.BigInteger,nullable=False),sa.Column("option_counts_json",sa.JSON,nullable=False),
        sa.Column("approved_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
    )
    op.create_index("ix_bank_selection","aptitude_question_bank",["status","category","topic","difficulty","times_used"])
    op.create_index("ix_bank_category_difficulty","aptitude_question_bank",["category","difficulty"])
    op.create_table(
        "aptitude_worker_heartbeats",
        sa.Column("worker_id",sa.String(180),primary_key=True),sa.Column("hostname",sa.String(180),nullable=False),
        sa.Column("process_id",sa.Integer,nullable=False),sa.Column("status",worker_status,nullable=False),
        sa.Column("current_job_id",sa.String(36)),sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("heartbeat_at",sa.DateTime(timezone=True),nullable=False),
    )
    op.create_index("ix_aptitude_worker_heartbeats_heartbeat_at","aptitude_worker_heartbeats",["heartbeat_at"])
    op.add_column("aptitude_answers",sa.Column("diagnostics_status",diagnostics_status,nullable=False,server_default="not_requested"))
    op.add_column("aptitude_background_jobs",sa.Column("dedupe_key",sa.String(190)))
    op.create_unique_constraint("uq_background_job_dedupe_key","aptitude_background_jobs",["dedupe_key"])
    op.add_column("aptitude_test_questions",sa.Column("source_bank_item_id",sa.String(36)))
    op.create_foreign_key("fk_test_question_bank_item","aptitude_test_questions","aptitude_question_bank",["source_bank_item_id"],["id"])
    op.create_index("ix_aptitude_test_questions_source_bank_item_id","aptitude_test_questions",["source_bank_item_id"])


def downgrade():
    op.drop_index("ix_aptitude_test_questions_source_bank_item_id",table_name="aptitude_test_questions")
    op.drop_constraint("fk_test_question_bank_item","aptitude_test_questions",type_="foreignkey")
    op.drop_column("aptitude_test_questions","source_bank_item_id")
    op.drop_constraint("uq_background_job_dedupe_key","aptitude_background_jobs",type_="unique")
    op.drop_column("aptitude_background_jobs","dedupe_key")
    op.drop_column("aptitude_answers","diagnostics_status")
    op.drop_table("aptitude_worker_heartbeats")
    op.drop_table("aptitude_question_bank")
