"""Add reasoning-before-answer evaluation fields.

Revision ID: 0006_reasoning_before_answer
Revises: 0005_adaptive_testing
"""
from alembic import op
import sqlalchemy as sa


revision="0006_reasoning_before_answer"
down_revision="0005_adaptive_testing"
branch_labels=None
depends_on=None


def upgrade():
    reasoning_quality=sa.Enum("strong","partial","weak","none",name="reasoning_quality")
    outcome_type=sa.Enum("correct_sound_reasoning","correct_flawed_reasoning","incorrect_close_reasoning","incorrect_flawed_reasoning","no_reasoning_given",name="answer_outcome_type")
    op.add_column("aptitude_answers",sa.Column("reasoning_text",sa.Text()))
    op.add_column("aptitude_answers",sa.Column("reasoning_quality",reasoning_quality))
    op.add_column("aptitude_answers",sa.Column("reasoning_feedback",sa.Text()))
    op.add_column("aptitude_answers",sa.Column("outcome_type",outcome_type))


def downgrade():
    op.drop_column("aptitude_answers","outcome_type")
    op.drop_column("aptitude_answers","reasoning_feedback")
    op.drop_column("aptitude_answers","reasoning_quality")
    op.drop_column("aptitude_answers","reasoning_text")
