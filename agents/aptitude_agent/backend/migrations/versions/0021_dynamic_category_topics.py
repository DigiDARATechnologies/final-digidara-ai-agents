"""Add last-topic rotation state for live Category Practice.

Revision ID: 0021_dynamic_category_topics
Revises: 0020_reasoning_diagnostics_status
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0021_dynamic_category_topics"
down_revision = "0020_reasoning_diagnostics_status"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "learner_last_topics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("learner_id", sa.String(128), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.String(80), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("topics_used", mysql.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("learner_id", "category_id", "level", name="uq_learner_last_topics_scope"),
    )
    op.create_index("ix_learner_last_topics_learner_id", "learner_last_topics", ["learner_id"])


def downgrade():
    op.drop_index("ix_learner_last_topics_learner_id", table_name="learner_last_topics")
    op.drop_table("learner_last_topics")
