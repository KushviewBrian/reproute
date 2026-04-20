"""phase 12 owner/employee reliability schema

Revision ID: 0009_owner_employee_reliability
Revises: 0008_blue_collar_owner_contact
Create Date: 2026-04-20
"""

from alembic import op

revision = "0009_owner_employee_reliability"
down_revision = "0008_blue_collar_owner_contact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE business ADD COLUMN IF NOT EXISTS employee_count_estimate INTEGER")
    op.execute("ALTER TABLE business ADD COLUMN IF NOT EXISTS employee_count_band TEXT")
    op.execute("ALTER TABLE business ADD COLUMN IF NOT EXISTS employee_count_source TEXT")
    op.execute("ALTER TABLE business ADD COLUMN IF NOT EXISTS employee_count_confidence NUMERIC(4,3)")
    op.execute("ALTER TABLE business ADD COLUMN IF NOT EXISTS employee_count_last_checked_at TIMESTAMPTZ")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS business_contact_candidate (
          id UUID PRIMARY KEY,
          business_id UUID NOT NULL REFERENCES business(id),
          field_key TEXT NOT NULL,
          value_text TEXT NULL,
          value_numeric INTEGER NULL,
          source TEXT NOT NULL,
          confidence NUMERIC(4,3) NULL,
          evidence_json JSONB NULL,
          observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          promoted_at TIMESTAMPTZ NULL,
          is_active BOOLEAN NOT NULL DEFAULT false,
          value_hash TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_bcc_business_field_source_hash
        ON business_contact_candidate (business_id, field_key, source, value_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bcc_business_field_active
        ON business_contact_candidate (business_id, field_key)
        WHERE is_active = true
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bcc_promoted_at
        ON business_contact_candidate (promoted_at)
        WHERE promoted_at IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_business_employee_count_band
        ON business (employee_count_band)
        WHERE employee_count_band IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_business_employee_count_band")
    op.execute("DROP INDEX IF EXISTS idx_bcc_promoted_at")
    op.execute("DROP INDEX IF EXISTS idx_bcc_business_field_active")
    op.execute("DROP INDEX IF EXISTS uq_bcc_business_field_source_hash")
    op.execute("DROP TABLE IF EXISTS business_contact_candidate")
    op.execute("ALTER TABLE business DROP COLUMN IF EXISTS employee_count_last_checked_at")
    op.execute("ALTER TABLE business DROP COLUMN IF EXISTS employee_count_confidence")
    op.execute("ALTER TABLE business DROP COLUMN IF EXISTS employee_count_source")
    op.execute("ALTER TABLE business DROP COLUMN IF EXISTS employee_count_band")
    op.execute("ALTER TABLE business DROP COLUMN IF EXISTS employee_count_estimate")
