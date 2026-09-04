"""Add automatic question-bank factory metadata and bank-question history.

Revision ID: 0016_bank_factory_history
Revises: 0015_category_practice
"""
from alembic import op
import sqlalchemy as sa


revision="0016_bank_factory_history"
down_revision="0015_category_practice"
branch_labels=None
depends_on=None


def upgrade():
    op.add_column("aptitude_question_bank",sa.Column("hint_text",sa.Text()))
    op.add_column("aptitude_question_bank",sa.Column("report_count",sa.Integer(),nullable=False,server_default="0"))
    op.add_column("aptitude_recent_question_hashes",sa.Column("bank_question_id",sa.String(36)))
    op.create_index("ix_recent_hash_bank_question","aptitude_recent_question_hashes",["bank_question_id"])
    op.create_foreign_key("fk_recent_hash_bank_question","aptitude_recent_question_hashes","aptitude_question_bank",["bank_question_id"],["id"])
    # Keep existing values valid while allowing automatic curation to archive
    # items without deleting their operational history.
    op.execute("ALTER TABLE aptitude_question_bank MODIFY status ENUM('draft','review','approved','retired','archived') NOT NULL DEFAULT 'draft'")


def downgrade():
    op.execute("UPDATE aptitude_question_bank SET status='retired' WHERE status='archived'")
    op.execute("ALTER TABLE aptitude_question_bank MODIFY status ENUM('draft','review','approved','retired') NOT NULL DEFAULT 'draft'")
    op.drop_constraint("fk_recent_hash_bank_question","aptitude_recent_question_hashes",type_="foreignkey")
    op.drop_index("ix_recent_hash_bank_question",table_name="aptitude_recent_question_hashes")
    op.drop_column("aptitude_recent_question_hashes","bank_question_id")
    op.drop_column("aptitude_question_bank","report_count")
    op.drop_column("aptitude_question_bank","hint_text")
