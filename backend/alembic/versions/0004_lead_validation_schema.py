"""add lead validation schema tables

Revision ID: 0004_lead_validation_schema
Revises: 0003_saved_lead_follow_up_fields
Create Date: 2026-04-17
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_lead_validation_schema"
down_revision = "0003_saved_lead_follow_up_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE lead_validation_run (
          id UUID PRIMARY KEY,
          business_id UUID NOT NULL REFERENCES business(id),
          user_id UUID REFERENCES "user"(id),
          requested_checks TEXT[],
          status TEXT NOT NULL DEFAULT 'queued',
          started_at TIMESTAMPTZ,
          finished_at TIMESTAMPTZ,
          error_message TEXT,
          created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_lead_validation_run_business_created ON lead_validation_run (business_id, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE lead_field_validation (
          id UUID PRIMARY KEY,
          business_id UUID NOT NULL REFERENCES business(id),
          field_name TEXT NOT NULL,
          value_current TEXT,
          value_normalized TEXT,
          state TEXT,
          confidence NUMERIC(5,2),
          evidence_json JSONB,
          failure_class TEXT,
          last_checked_at TIMESTAMPTZ,
          next_check_at TIMESTAMPTZ,
          pinned_by_user BOOLEAN NOT NULL DEFAULT FALSE,
          created_at TIMESTAMPTZ DEFAULT now(),
          updated_at TIMESTAMPTZ DEFAULT now(),
          UNIQUE (business_id, field_name)
        )
        """
    )
    op.execute("CREATE INDEX idx_lead_field_validation_business_id ON lead_field_validation (business_id)")
    op.execute("CREATE INDEX idx_lead_field_validation_next_check_at ON lead_field_validation (next_check_at)")

    op.execute(
        """
        CREATE TABLE lead_expansion_candidate (
          id UUID PRIMARY KEY,
          source_business_id UUID NOT NULL REFERENCES business(id),
          candidate_payload JSONB NOT NULL,
          dedupe_key TEXT NOT NULL UNIQUE,
          confidence NUMERIC(5,2),
          source_url TEXT,
          status TEXT NOT NULL DEFAULT 'new',
          created_at TIMESTAMPTZ DEFAULT now(),
          expires_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX idx_lead_expansion_candidate_status ON lead_expansion_candidate (status)")
    op.execute("CREATE INDEX idx_lead_expansion_candidate_expires_at ON lead_expansion_candidate (expires_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS lead_expansion_candidate")
    op.execute("DROP TABLE IF EXISTS lead_field_validation")
    op.execute("DROP TABLE IF EXISTS lead_validation_run")
