"""Store the learner's IANA timezone with each assessment attempt.

Revision ID: 0025_test_timezone
Revises: 0024_technical_language
"""
from alembic import op
import sqlalchemy as sa


revision = "0025_test_timezone"
down_revision = "0024_technical_language"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("aptitude_tests", sa.Column("timezone", sa.String(length=80), nullable=True))


def downgrade():
    op.drop_column("aptitude_tests", "timezone")
