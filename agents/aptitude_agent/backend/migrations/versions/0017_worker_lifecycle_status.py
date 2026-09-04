"""Track clean worker shutdown and prune stale worker heartbeats.

Revision ID: 0017_worker_lifecycle_status
Revises: 0016_bank_factory_history
"""
from alembic import op


revision="0017_worker_lifecycle_status"
down_revision="0016_bank_factory_history"
branch_labels=None
depends_on=None


def upgrade():
    op.execute(
        "ALTER TABLE aptitude_worker_heartbeats MODIFY status "
        "ENUM('starting','idle','working','stopping','stopped','dead') NOT NULL DEFAULT 'starting'"
    )


def downgrade():
    op.execute("UPDATE aptitude_worker_heartbeats SET status='stopping' WHERE status IN ('stopped','dead')")
    op.execute(
        "ALTER TABLE aptitude_worker_heartbeats MODIFY status "
        "ENUM('starting','idle','working','stopping') NOT NULL DEFAULT 'starting'"
    )
