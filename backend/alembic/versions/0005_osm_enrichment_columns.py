"""add OSM enrichment columns to business

Revision ID: 0005_osm_enrichment_columns
Revises: 0004_lead_validation_schema
Create Date: 2026-04-18
"""

from alembic import op

revision = "0005_osm_enrichment_columns"
down_revision = "0004_lead_validation_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE business
          ADD COLUMN IF NOT EXISTS osm_enriched_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS osm_phone TEXT,
          ADD COLUMN IF NOT EXISTS osm_website TEXT,
          ADD COLUMN IF NOT EXISTS city_license_verified_at TIMESTAMPTZ
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_business_osm_enriched_at ON business (osm_enriched_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_business_osm_enriched_at")
    op.execute(
        """
        ALTER TABLE business
          DROP COLUMN IF EXISTS osm_enriched_at,
          DROP COLUMN IF EXISTS osm_phone,
          DROP COLUMN IF EXISTS osm_website,
          DROP COLUMN IF EXISTS city_license_verified_at
        """
    )
