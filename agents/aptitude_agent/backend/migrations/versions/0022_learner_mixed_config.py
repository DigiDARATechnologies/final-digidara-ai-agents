"""Add per-learner Mixed Test counts and per-attempt snapshots.

Revision ID: 0022_learner_mixed_config
Revises: 0021_dynamic_category_topics
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0022_learner_mixed_config"
down_revision = "0021_dynamic_category_topics"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "learner_mixed_test_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "learner_id", sa.String(128),
            sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("category_id", sa.String(50), nullable=False),
        sa.Column("category_name", sa.String(80), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "learner_id", "category_id", name="uq_learner_mixed_test_category",
        ),
        sa.CheckConstraint(
            "question_count >= 0 AND question_count <= 10",
            name="ck_learner_mixed_question_count",
        ),
    )
    op.create_index(
        "ix_learner_mixed_test_config_learner_id",
        "learner_mixed_test_config", ["learner_id"],
    )
    op.add_column(
        "aptitude_tests",
        sa.Column("mixed_category_counts", mysql.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("aptitude_tests", "mixed_category_counts")
    op.drop_index(
        "ix_learner_mixed_test_config_learner_id",
        table_name="learner_mixed_test_config",
    )
    op.drop_table("learner_mixed_test_config")
