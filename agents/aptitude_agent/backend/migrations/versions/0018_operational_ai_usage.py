"""Allow AI usage records for system/background operations.

Revision ID: 0018_operational_ai_usage
Revises: 0017_worker_lifecycle_status
"""
from alembic import op


revision="0018_operational_ai_usage"
down_revision="0017_worker_lifecycle_status"
branch_labels=None
depends_on=None


def upgrade():
    op.execute("ALTER TABLE aptitude_ai_usage_events MODIFY student_id VARCHAR(128) NULL")


def downgrade():
    op.execute("DELETE FROM aptitude_ai_usage_events WHERE student_id IS NULL")
    op.execute("ALTER TABLE aptitude_ai_usage_events MODIFY student_id VARCHAR(128) NOT NULL")
