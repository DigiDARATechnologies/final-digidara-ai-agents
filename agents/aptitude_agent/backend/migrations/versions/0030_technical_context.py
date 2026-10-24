"""Snapshot signup role and skills on aptitude tests.

Revision ID: 0030_technical_context
Revises: 0029_mixed_min_zero
"""
from alembic import op
import sqlalchemy as sa


revision = "0030_technical_context"
down_revision = "0029_mixed_min_zero"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("aptitude_tests", sa.Column("technical_context", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("aptitude_tests", "technical_context")
