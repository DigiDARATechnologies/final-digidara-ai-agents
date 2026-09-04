"""Serialize Groq-backed question-bank replenishment across workers.

Revision ID: 0019_bank_generation_lease
Revises: 0018_operational_ai_usage
"""
from alembic import op
import sqlalchemy as sa


revision="0019_bank_generation_lease"
down_revision="0018_operational_ai_usage"
branch_labels=None
depends_on=None


def upgrade():
    op.create_table(
        "aptitude_bank_generation_leases",
        sa.Column("name",sa.String(80),primary_key=True),
        sa.Column("locked_by",sa.String(180)),
        sa.Column("locked_until",sa.DateTime(timezone=True)),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
    )
    op.execute("INSERT INTO aptitude_bank_generation_leases (name, updated_at) VALUES ('pool_replenish', UTC_TIMESTAMP())")


def downgrade():
    op.drop_table("aptitude_bank_generation_leases")
