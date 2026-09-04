"""Add fixed-level category practice assessments.

Revision ID: 0015_category_practice
Revises: 0014_sanitize_internal_metadata
"""
from alembic import op
import sqlalchemy as sa


revision="0015_category_practice"
down_revision="0014_sanitize_internal_metadata"
branch_labels=None
depends_on=None


def upgrade():
    op.add_column("aptitude_tests",sa.Column("test_mode",sa.Enum("mixed","category_practice",name="test_mode"),nullable=False,server_default="mixed"))
    op.add_column("aptitude_tests",sa.Column("selected_category",sa.String(80)))
    op.add_column("aptitude_tests",sa.Column("selected_level",sa.Enum("Beginner","Intermediate","Advanced",name="practice_level")))
    op.create_index("ix_aptitude_tests_test_mode","aptitude_tests",["test_mode"])


def downgrade():
    op.drop_index("ix_aptitude_tests_test_mode",table_name="aptitude_tests")
    op.drop_column("aptitude_tests","selected_level")
    op.drop_column("aptitude_tests","selected_category")
    op.drop_column("aptitude_tests","test_mode")
