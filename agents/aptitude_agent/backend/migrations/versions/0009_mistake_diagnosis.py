"""Add mistake-pattern diagnosis fields.

Revision ID: 0009_mistake_diagnosis
Revises: 0008_confidence_rating
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_mistake_diagnosis"
down_revision = "0008_confidence_rating"
branch_labels = None
depends_on = None


def upgrade():
    mistake_type = sa.Enum(
        "careless_slip",
        "conceptual_gap",
        "time_pressure",
        "not_applicable",
        name="mistake_type",
    )
    op.add_column("aptitude_answers", sa.Column("mistake_type", mistake_type))
    op.add_column("aptitude_answers", sa.Column("mistake_explanation", sa.Text()))


def downgrade():
    op.drop_column("aptitude_answers", "mistake_explanation")
    op.drop_column("aptitude_answers", "mistake_type")
