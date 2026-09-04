"""Require three to ten questions in every Mixed Test category.

Revision ID: 0023_mixed_min_three
Revises: 0022_learner_mixed_config
"""
from alembic import op


revision = "0023_mixed_min_three"
down_revision = "0022_learner_mixed_config"
branch_labels = None
depends_on = None


def upgrade():
    # Preserve each learner's choices while lifting legacy excluded/low values
    # to the new mandatory minimum before tightening the constraint.
    op.execute(
        "UPDATE learner_mixed_test_config "
        "SET question_count = 3 WHERE question_count < 3"
    )
    op.drop_constraint(
        "ck_learner_mixed_question_count",
        "learner_mixed_test_config",
        type_="check",
    )
    op.create_check_constraint(
        "ck_learner_mixed_question_count",
        "learner_mixed_test_config",
        "question_count >= 3 AND question_count <= 10",
    )


def downgrade():
    op.drop_constraint(
        "ck_learner_mixed_question_count",
        "learner_mixed_test_config",
        type_="check",
    )
    op.create_check_constraint(
        "ck_learner_mixed_question_count",
        "learner_mixed_test_config",
        "question_count >= 0 AND question_count <= 10",
    )
