"""add is_blue_collar and owner contact fields

Revision ID: 0008_blue_collar_and_owner_contact
Revises: 0007_scoring_geo_key_and_indexes
Create Date: 2026-04-19
"""

from alembic import op

revision = "0008_blue_collar_and_owner_contact"
down_revision = "0007_scoring_geo_key_and_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add each column individually — multi-column ADD COLUMN IF NOT EXISTS
    # in a single ALTER TABLE is rejected by some PostgreSQL driver versions.
    op.execute(
        "ALTER TABLE business ADD COLUMN IF NOT EXISTS is_blue_collar BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE business ADD COLUMN IF NOT EXISTS owner_name TEXT"
    )
    op.execute(
        "ALTER TABLE business ADD COLUMN IF NOT EXISTS owner_name_source TEXT"
    )
    op.execute(
        "ALTER TABLE business ADD COLUMN IF NOT EXISTS owner_name_confidence NUMERIC(4,3)"
    )
    op.execute(
        "ALTER TABLE business ADD COLUMN IF NOT EXISTS owner_name_last_checked_at TIMESTAMPTZ"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_business_is_blue_collar ON business (is_blue_collar)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_business_owner_name ON business (owner_name) WHERE owner_name IS NOT NULL"
    )

    # Backfill is_blue_collar from existing insurance_class values.
    op.execute(
        """
        UPDATE business
           SET is_blue_collar = TRUE
         WHERE insurance_class IN ('Auto Service', 'Contractor / Trades', 'Personal Services')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_business_owner_name")
    op.execute("DROP INDEX IF EXISTS idx_business_is_blue_collar")
    op.execute("ALTER TABLE business DROP COLUMN IF EXISTS owner_name_last_checked_at")
    op.execute("ALTER TABLE business DROP COLUMN IF EXISTS owner_name_confidence")
    op.execute("ALTER TABLE business DROP COLUMN IF EXISTS owner_name_source")
    op.execute("ALTER TABLE business DROP COLUMN IF EXISTS owner_name")
    op.execute("ALTER TABLE business DROP COLUMN IF EXISTS is_blue_collar")
