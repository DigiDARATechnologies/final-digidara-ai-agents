"""Add adaptive testing state and weighted scoring.

Revision ID: 0005_adaptive_testing
Revises: 0004_native_auth
"""
from alembic import op
import sqlalchemy as sa


revision="0005_adaptive_testing"
down_revision="0004_native_auth"
branch_labels=None
depends_on=None


def upgrade():
    op.add_column("aptitude_tests",sa.Column("focus_category",sa.String(80)))
    op.add_column("aptitude_tests",sa.Column("weighted_score",sa.Numeric(7,2),nullable=False,server_default="0"))
    op.add_column("aptitude_tests",sa.Column("max_weighted_score",sa.Numeric(7,2),nullable=False,server_default="0"))
    op.add_column("aptitude_test_questions",sa.Column("difficulty_reason",sa.String(255)))


def downgrade():
    op.drop_column("aptitude_test_questions","difficulty_reason")
    op.drop_column("aptitude_tests","max_weighted_score")
    op.drop_column("aptitude_tests","weighted_score")
    op.drop_column("aptitude_tests","focus_category")
