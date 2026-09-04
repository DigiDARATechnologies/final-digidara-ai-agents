"""Add explicit reasoning outcomes and provider availability states."""
from alembic import op
import sqlalchemy as sa

revision="0020_reasoning_diagnostics_status"
down_revision="0019_bank_generation_lease"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("ALTER TABLE aptitude_answers MODIFY COLUMN diagnostics_status ENUM('not_requested','pending','completed','unavailable','failed') NOT NULL DEFAULT 'not_requested'")
    op.add_column("aptitude_answers",sa.Column("reasoning_verdict",sa.Enum("correct","incorrect","partially_correct",name="reasoning_verdict"),nullable=True))
    op.add_column("aptitude_answers",sa.Column("reasoning_confidence",sa.Float(),nullable=True))
    op.add_column("aptitude_answers",sa.Column("diagnostics_error",sa.Text(),nullable=True))

def downgrade():
    op.drop_column("aptitude_answers","diagnostics_error")
    op.drop_column("aptitude_answers","reasoning_confidence")
    op.drop_column("aptitude_answers","reasoning_verdict")
    op.execute("ALTER TABLE aptitude_answers MODIFY COLUMN diagnostics_status ENUM('not_requested','pending','completed','failed') NOT NULL DEFAULT 'not_requested'")
