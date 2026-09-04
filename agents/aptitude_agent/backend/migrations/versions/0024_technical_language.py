"""Persist the selected Technical Aptitude language.

Revision ID: 0024_technical_language
Revises: 0023_mixed_min_three
"""
from alembic import op
import sqlalchemy as sa


revision = "0024_technical_language"
down_revision = "0023_mixed_min_three"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "aptitude_tests",
        sa.Column("technical_language",sa.String(length=20),nullable=True),
    )


def downgrade():
    op.drop_column("aptitude_tests","technical_language")
