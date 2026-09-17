"""Add a server-authoritative overall timer to aptitude attempts."""
from alembic import op
import sqlalchemy as sa

revision = "0027_overall_test_timer"
down_revision = "0026_question_navigation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("aptitude_tests", sa.Column("assessment_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("aptitude_tests", sa.Column("total_duration_seconds", sa.Integer(), nullable=True))
    op.add_column("aptitude_tests", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("aptitude_tests", "expires_at")
    op.drop_column("aptitude_tests", "total_duration_seconds")
    op.drop_column("aptitude_tests", "assessment_started_at")
