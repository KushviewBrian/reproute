"""add import jobs table

Revision ID: 0002_import_jobs
Revises: 0001_initial
Create Date: 2026-04-16
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_import_jobs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE import_job (
          id UUID PRIMARY KEY,
          user_id UUID REFERENCES "user"(id),
          source_type TEXT NOT NULL DEFAULT 'overture_parquet',
          parquet_path TEXT,
          label TEXT,
          bbox TEXT,
          status TEXT NOT NULL DEFAULT 'queued',
          error_message TEXT,
          result_json JSONB,
          started_at TIMESTAMPTZ,
          finished_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ DEFAULT now(),
          updated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_import_job_status ON import_job (status)")
    op.execute("CREATE INDEX idx_import_job_created_at ON import_job (created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS import_job")
