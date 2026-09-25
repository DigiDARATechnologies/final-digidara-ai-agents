"""Allow zero questions for individual Mixed Test categories.

Revision ID: 0029_mixed_min_zero
Revises: 0028_dpdp_consent
"""
from alembic import op


revision = "0029_mixed_min_zero"
down_revision = "0028_dpdp_consent"
branch_labels = None
depends_on = None


def upgrade():
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


def downgrade():
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
