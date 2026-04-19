"""add scoring v2 shadow columns and feedback priors

Revision ID: 0006_scoring_v2_shadow_schema
Revises: 0005_osm_enrichment_columns
Create Date: 2026-04-19
"""

from alembic import op

revision = "0006_scoring_v2_shadow_schema"
down_revision = "0005_osm_enrichment_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE lead_score
          ADD COLUMN IF NOT EXISTS fit_score_v2 SMALLINT CHECK (fit_score_v2 BETWEEN 0 AND 100),
          ADD COLUMN IF NOT EXISTS distance_score_v2 SMALLINT CHECK (distance_score_v2 BETWEEN 0 AND 100),
          ADD COLUMN IF NOT EXISTS actionability_score_v2 SMALLINT CHECK (actionability_score_v2 BETWEEN 0 AND 100),
          ADD COLUMN IF NOT EXISTS feedback_score_v2 SMALLINT CHECK (feedback_score_v2 BETWEEN 0 AND 100),
          ADD COLUMN IF NOT EXISTS final_score_v2 SMALLINT CHECK (final_score_v2 BETWEEN 0 AND 100),
          ADD COLUMN IF NOT EXISTS calibration_version TEXT,
          ADD COLUMN IF NOT EXISTS score_explanation_v2_json JSONB
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS scoring_feedback_prior (
          id UUID PRIMARY KEY,
          calibration_version TEXT NOT NULL,
          insurance_class TEXT,
          has_phone BOOLEAN,
          has_website BOOLEAN,
          distance_band TEXT NOT NULL,
          sample_size INTEGER NOT NULL DEFAULT 0,
          save_count INTEGER NOT NULL DEFAULT 0,
          contacted_count INTEGER NOT NULL DEFAULT 0,
          prior_save NUMERIC(6,5) NOT NULL DEFAULT 0,
          prior_contact NUMERIC(6,5) NOT NULL DEFAULT 0,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
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
        "CREATE INDEX IF NOT EXISTS idx_scoring_feedback_prior_version ON scoring_feedback_prior (calibration_version)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_scoring_feedback_prior_version")
    op.execute("DROP INDEX IF EXISTS uq_scoring_feedback_prior_segment")
    op.execute("DROP TABLE IF EXISTS scoring_feedback_prior")
    op.execute(
        """
        ALTER TABLE lead_score
          DROP COLUMN IF EXISTS fit_score_v2,
          DROP COLUMN IF EXISTS distance_score_v2,
          DROP COLUMN IF EXISTS actionability_score_v2,
          DROP COLUMN IF EXISTS feedback_score_v2,
          DROP COLUMN IF EXISTS final_score_v2,
          DROP COLUMN IF EXISTS calibration_version,
          DROP COLUMN IF EXISTS score_explanation_v2_json
        """
    )
