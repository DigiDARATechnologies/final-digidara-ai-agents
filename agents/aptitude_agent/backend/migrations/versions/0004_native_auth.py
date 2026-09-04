"""Add native AptiDARA account credentials.

Revision ID: 0004_native_auth
Revises: 0003_edit_profile
"""
from alembic import op
import sqlalchemy as sa

revision="0004_native_auth"
down_revision="0003_edit_profile"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("students",sa.Column("password_hash",sa.String(255)))
    op.add_column("students",sa.Column("token_version",sa.Integer,nullable=False,server_default="0"))
    op.create_unique_constraint("uq_students_email","students",["email"])

def downgrade():
    op.drop_constraint("uq_students_email","students",type_="unique")
    op.drop_column("students","token_version")
    op.drop_column("students","password_hash")
