"""Remove difficulty-weighted scoring.

Revision ID: 0011_remove_weighted_scoring
Revises: 0010_authoritative_evaluation
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_remove_weighted_scoring"
down_revision = "0010_authoritative_evaluation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE aptitude_tests "
        "SET percentage = CASE "
        "WHEN total_questions > 0 THEN ROUND(correct_count * 100.0 / total_questions, 2) "
        "ELSE 0 END"
    )
    op.drop_column("aptitude_tests", "max_weighted_score")
    op.drop_column("aptitude_tests", "weighted_score")


def downgrade():
    op.add_column(
        "aptitude_tests",
        sa.Column("weighted_score", sa.Numeric(7, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "aptitude_tests",
        sa.Column("max_weighted_score", sa.Numeric(7, 2), nullable=False, server_default="0"),
    )
