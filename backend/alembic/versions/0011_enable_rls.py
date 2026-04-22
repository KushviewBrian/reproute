"""Enable Row-Level Security on all public tables

Revision ID: 0011_enable_rls
Revises: 0010_optimization_indexes
Create Date: 2026-04-21

Why: Supabase exposes every table via PostgREST under the anon/authenticated
roles. Without RLS, anyone who discovers the project URL can read, write, or
delete all rows directly through the Supabase REST API — bypassing FastAPI
entirely. Enabling RLS with a deny-all fallback policy closes this exposure.

How this interacts with the FastAPI backend:
- The backend connects with the Postgres service-role credential (DATABASE_URL),
  which is a superuser-equivalent role that bypasses RLS entirely. No backend
  query is affected by these policies.
- PostgREST/supabase-js connections use the `anon` or `authenticated` role,
  which are subject to RLS. The deny-all policy blocks them with no exceptions,
  since RepRoute never uses the Supabase client SDK for data access.
"""

from alembic import op

# All tables in the public schema that need RLS enabled.
_TABLES = [
    "user",
    "business",
    "route",
    "route_candidate",
    "lead_score",
    "saved_lead",
    "note",
    "lead_validation_run",
    "lead_field_validation",
    "lead_expansion_candidate",
    "scoring_feedback_prior",
    "business_contact_candidate",
]

revision = "0011_enable_rls"
down_revision = "0010_optimization_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in _TABLES:
        # Enable RLS — subsequent access requires an explicit permissive policy.
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        # Deny-all fallback: no anon/authenticated role can read or write any row.
        # The backend's service-role credential bypasses RLS and is unaffected.
        op.execute(
            f'CREATE POLICY "deny_all_public_{table}" ON "{table}" '
            f'AS RESTRICTIVE TO PUBLIC USING (false) WITH CHECK (false)'
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f'DROP POLICY IF EXISTS "deny_all_public_{table}" ON "{table}"')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
