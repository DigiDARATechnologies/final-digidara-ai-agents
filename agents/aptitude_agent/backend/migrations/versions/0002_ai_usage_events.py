"""Add persistent Groq token and cost usage events.

Revision ID: 0002_ai_usage
Revises: 0001_mysql_initial
"""
from alembic import op
import sqlalchemy as sa

revision="0002_ai_usage"
down_revision="0001_mysql_initial"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("aptitude_ai_usage_events",
      sa.Column("id",sa.BigInteger,primary_key=True,autoincrement=True),
      sa.Column("student_id",sa.String(128),sa.ForeignKey("students.id"),nullable=False),
      sa.Column("test_id",sa.String(36),sa.ForeignKey("aptitude_tests.id")),
      sa.Column("question_id",sa.String(36),sa.ForeignKey("aptitude_test_questions.id")),
      sa.Column("operation",sa.String(40),nullable=False),
      sa.Column("model",sa.String(100),nullable=False),
      sa.Column("input_tokens",sa.Integer,nullable=False,server_default="0"),
      sa.Column("output_tokens",sa.Integer,nullable=False,server_default="0"),
      sa.Column("total_tokens",sa.Integer,nullable=False,server_default="0"),
      sa.Column("estimated_cost_usd",sa.Numeric(14,8),nullable=False,server_default="0"),
      sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_ai_usage_student_created","aptitude_ai_usage_events",["student_id","created_at"])
    op.create_index("ix_ai_usage_test","aptitude_ai_usage_events",["test_id"])
    op.create_index("ix_ai_usage_question","aptitude_ai_usage_events",["question_id"])

def downgrade():
    op.drop_table("aptitude_ai_usage_events")
