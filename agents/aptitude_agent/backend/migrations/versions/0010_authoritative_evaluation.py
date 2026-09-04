"""Add authoritative answer evaluation source.

Revision ID: 0010_authoritative_evaluation
Revises: 0009_mistake_diagnosis
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_authoritative_evaluation"
down_revision = "0009_mistake_diagnosis"
branch_labels = None
depends_on = None


old_source = sa.Enum("groq", "fallback", "fallback_consistency", "timeout", name="evaluation_source")
new_source = sa.Enum("groq", "fallback", "fallback_consistency", "authoritative", "timeout", name="evaluation_source")


def upgrade():
    op.alter_column("aptitude_answers", "evaluation_source", existing_type=old_source, type_=new_source, existing_nullable=False)


def downgrade():
    op.execute("UPDATE aptitude_answers SET evaluation_source='fallback' WHERE evaluation_source='authoritative'")
    op.alter_column("aptitude_answers", "evaluation_source", existing_type=new_source, type_=old_source, existing_nullable=False)
