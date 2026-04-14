"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-04-14
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.execute(
        """
        CREATE TABLE "user" (
          id UUID PRIMARY KEY,
          email TEXT NOT NULL UNIQUE,
          full_name TEXT,
          organization TEXT,
          created_at TIMESTAMPTZ DEFAULT now(),
          updated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE business (
          id UUID PRIMARY KEY,
          external_source TEXT NOT NULL,
          external_id TEXT NOT NULL,
          name TEXT NOT NULL,
          normalized_name TEXT,
          brand_name TEXT,
          category_primary TEXT,
          category_secondary TEXT,
          insurance_class TEXT,
          address_line1 TEXT,
          city TEXT,
          state TEXT,
          postal_code TEXT,
          country TEXT DEFAULT 'US',
          phone TEXT,
          website TEXT,
          operating_status TEXT,
          confidence_score NUMERIC(4,3),
          geom GEOGRAPHY(Point, 4326) NOT NULL,
          has_phone BOOLEAN DEFAULT FALSE,
          has_website BOOLEAN DEFAULT FALSE,
          has_address BOOLEAN DEFAULT FALSE,
          source_payload_json JSONB,
          created_at TIMESTAMPTZ DEFAULT now(),
          updated_at TIMESTAMPTZ DEFAULT now(),
          last_seen_at TIMESTAMPTZ,
          last_validated_at TIMESTAMPTZ,
          UNIQUE (external_source, external_id)
        )
        """
    )
    op.execute("CREATE INDEX idx_business_geom ON business USING GIST (geom)")
    op.execute("CREATE INDEX idx_business_insurance_class ON business (insurance_class)")
    op.execute("CREATE INDEX idx_business_operating_status ON business (operating_status)")

    op.execute(
        """
        CREATE TABLE route (
          id UUID PRIMARY KEY,
          user_id UUID REFERENCES "user"(id),
          origin_label TEXT,
          destination_label TEXT,
          origin_lat NUMERIC(10,7) NOT NULL,
          origin_lng NUMERIC(10,7) NOT NULL,
          destination_lat NUMERIC(10,7) NOT NULL,
          destination_lng NUMERIC(10,7) NOT NULL,
          route_geom GEOGRAPHY(LineString, 4326),
          route_distance_meters INTEGER,
          route_duration_seconds INTEGER,
          corridor_width_meters INTEGER DEFAULT 1609,
          ors_response_json JSONB,
          created_at TIMESTAMPTZ DEFAULT now(),
          updated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_route_geom ON route USING GIST (route_geom)")
    op.execute("CREATE INDEX idx_route_user ON route (user_id)")

    op.execute(
        """
        CREATE TABLE route_candidate (
          id UUID PRIMARY KEY,
          route_id UUID NOT NULL REFERENCES route(id) ON DELETE CASCADE,
          business_id UUID NOT NULL REFERENCES business(id),
          distance_from_route_m NUMERIC(10,2),
          within_corridor BOOLEAN DEFAULT TRUE,
          created_at TIMESTAMPTZ DEFAULT now(),
          UNIQUE (route_id, business_id)
        )
        """
    )
    op.execute("CREATE INDEX idx_route_candidate_route ON route_candidate (route_id)")

    op.execute(
        """
        CREATE TABLE lead_score (
          id UUID PRIMARY KEY,
          route_id UUID NOT NULL REFERENCES route(id) ON DELETE CASCADE,
          business_id UUID NOT NULL REFERENCES business(id),
          fit_score SMALLINT CHECK (fit_score BETWEEN 0 AND 100),
          distance_score SMALLINT CHECK (distance_score BETWEEN 0 AND 100),
          actionability_score SMALLINT CHECK (actionability_score BETWEEN 0 AND 100),
          final_score SMALLINT CHECK (final_score BETWEEN 0 AND 100),
          score_version TEXT DEFAULT 'v1',
          score_explanation_json JSONB,
          created_at TIMESTAMPTZ DEFAULT now(),
          UNIQUE (route_id, business_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE saved_lead (
          id UUID PRIMARY KEY,
          user_id UUID NOT NULL REFERENCES "user"(id),
          route_id UUID REFERENCES route(id),
          business_id UUID NOT NULL REFERENCES business(id),
          status TEXT DEFAULT 'saved',
          priority SMALLINT DEFAULT 0,
          created_at TIMESTAMPTZ DEFAULT now(),
          updated_at TIMESTAMPTZ DEFAULT now(),
          UNIQUE (user_id, business_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE note (
          id UUID PRIMARY KEY,
          user_id UUID NOT NULL REFERENCES "user"(id),
          business_id UUID NOT NULL REFERENCES business(id),
          route_id UUID REFERENCES route(id),
          note_text TEXT NOT NULL,
          outcome_status TEXT,
          next_action TEXT,
          created_at TIMESTAMPTZ DEFAULT now(),
          updated_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_note_business ON note (business_id)")
    op.execute("CREATE INDEX idx_note_user ON note (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS note")
    op.execute("DROP TABLE IF EXISTS saved_lead")
    op.execute("DROP TABLE IF EXISTS lead_score")
    op.execute("DROP TABLE IF EXISTS route_candidate")
    op.execute("DROP TABLE IF EXISTS route")
    op.execute("DROP TABLE IF EXISTS business")
    op.execute("DROP TABLE IF EXISTS \"user\"")
