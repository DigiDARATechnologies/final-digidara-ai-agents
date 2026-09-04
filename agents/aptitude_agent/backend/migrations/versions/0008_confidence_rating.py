"""Add optional per-answer confidence ratings.

Revision ID: 0008_confidence_rating
Revises: 0007_conceptual_hints
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_confidence_rating"
down_revision = "0007_conceptual_hints"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("aptitude_answers", sa.Column("confidence_rating", sa.Integer()))
    op.create_check_constraint(
        "ck_answer_confidence_rating",
        "aptitude_answers",
        "confidence_rating IS NULL OR (confidence_rating >= 1 AND confidence_rating <= 5)",
    )


def downgrade():
    op.drop_constraint("ck_answer_confidence_rating", "aptitude_answers", type_="check")
    op.drop_column("aptitude_answers", "confidence_rating")
