"""add geo key to scoring feedback priors

Revision ID: 0007_scoring_geo_key_and_indexes
Revises: 0006_scoring_v2_shadow_schema
Create Date: 2026-04-19
"""

from alembic import op

revision = "0007_scoring_geo_key_and_indexes"
down_revision = "0006_scoring_v2_shadow_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE scoring_feedback_prior
          ADD COLUMN IF NOT EXISTS geo_key TEXT NOT NULL DEFAULT 'global'
        """
    )
    op.execute("DROP INDEX IF EXISTS uq_scoring_feedback_prior_segment")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_scoring_feedback_prior_segment
          ON scoring_feedback_prior (
            calibration_version,
            geo_key,
            insurance_class,
            has_phone,
            has_website,
            distance_band
          )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_scoring_feedback_prior_geo_version ON scoring_feedback_prior (geo_key, calibration_version)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_scoring_feedback_prior_geo_version")
    op.execute("DROP INDEX IF EXISTS uq_scoring_feedback_prior_segment")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_scoring_feedback_prior_segment
          ON scoring_feedback_prior (
            calibration_version,
            insurance_class,
            has_phone,
            has_website,
            distance_band
          )
        """
    )
    op.execute(
        """
        ALTER TABLE scoring_feedback_prior
          DROP COLUMN IF EXISTS geo_key
        """
    )
