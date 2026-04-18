"""add saved lead follow-up fields

Revision ID: 0003_saved_lead_follow_up_fields
Revises: 0002_import_jobs
Create Date: 2026-04-17
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_saved_lead_follow_up_fields"
down_revision = "0002_import_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE saved_lead
        ADD COLUMN IF NOT EXISTS next_follow_up_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS last_contact_attempt_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_saved_lead_next_follow_up_at
        ON saved_lead (next_follow_up_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_saved_lead_next_follow_up_at")
    op.execute(
        """
        ALTER TABLE saved_lead
        DROP COLUMN IF EXISTS next_follow_up_at,
        DROP COLUMN IF EXISTS last_contact_attempt_at
        """
    )
