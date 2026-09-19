"""Add DPDP (Digital Personal Data Protection Act) consent tracking to students."""
from alembic import op
import sqlalchemy as sa

revision = "0028_dpdp_consent"
down_revision = "0027_overall_test_timer"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("students", sa.Column("data_consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("students", sa.Column("data_consent_version", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("students", "data_consent_version")
    op.drop_column("students", "data_consent_at")
