"""Add editable learner profile fields and MySQL-backed photo.

Revision ID: 0003_edit_profile
Revises: 0002_ai_usage
"""
from alembic import op
import sqlalchemy as sa

revision="0003_edit_profile"
down_revision="0002_ai_usage"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("students",sa.Column("phone",sa.String(24)))
    op.add_column("students",sa.Column("profile_photo",sa.LargeBinary(length=3*1024*1024)))
    op.add_column("students",sa.Column("profile_photo_mime",sa.String(40)))

def downgrade():
    op.drop_column("students","profile_photo_mime")
    op.drop_column("students","profile_photo")
    op.drop_column("students","phone")
