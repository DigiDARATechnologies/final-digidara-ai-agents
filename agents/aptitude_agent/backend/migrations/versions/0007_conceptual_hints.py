"""Add conceptual hint tracking and per-test budgets.

Revision ID: 0007_conceptual_hints
Revises: 0006_reasoning_before_answer
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_conceptual_hints"
down_revision = "0006_reasoning_before_answer"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "aptitude_tests",
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "aptitude_tests",
        sa.Column("hints_allowed", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column("aptitude_test_questions", sa.Column("hint_text", sa.Text()))
    op.add_column(
        "aptitude_test_questions",
        sa.Column("hint_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "aptitude_test_questions",
        sa.Column("hint_requested_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_column("aptitude_test_questions", "hint_requested_at")
    op.drop_column("aptitude_test_questions", "hint_requested")
    op.drop_column("aptitude_test_questions", "hint_text")
    op.drop_column("aptitude_tests", "hints_allowed")
    op.drop_column("aptitude_tests", "hints_used")
