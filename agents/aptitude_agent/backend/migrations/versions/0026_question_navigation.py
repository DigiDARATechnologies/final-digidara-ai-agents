"""Persist per-question navigation and paused timer state."""
from alembic import op
import sqlalchemy as sa

revision = "0026_question_navigation"
down_revision = "0025_test_timezone"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("aptitude_test_questions", sa.Column("time_spent_seconds", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("aptitude_test_questions", sa.Column("visited", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.alter_column("aptitude_test_questions", "time_spent_seconds", server_default=None)
    op.alter_column("aptitude_test_questions", "visited", server_default=None)


def downgrade():
    op.drop_column("aptitude_test_questions", "visited")
    op.drop_column("aptitude_test_questions", "time_spent_seconds")
