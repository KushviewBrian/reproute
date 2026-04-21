# Supabase RLS Warning: `public.alembic_version`

## Issue
Supabase reports:
- **RLS Disabled in Public**
- Entity: `public.alembic_version`

This means the table is in a schema exposed to PostgREST (`public`) but does not have Row Level Security enabled.

## Why This Happens
- `alembic_version` is an internal migration-tracking table created by Alembic.
- Supabase security checks flag exposed-schema tables without RLS, even if your frontend never queries them.

## Risk
- Usually low for this specific table (it only stores migration version state), but it is still a security posture warning and should be cleaned up.

## Recommended Fix
Enable RLS on the table:

```sql
alter table public.alembic_version enable row level security;
```

Optionally also revoke API roles from direct table access:

```sql
revoke all on table public.alembic_version from anon, authenticated;
```

## Longer-Term Hardening
- Keep internal/backend-only tables out of exposed schemas when possible.
- Or limit exposed schemas in Supabase API settings so internal tables are not covered by PostgREST exposure rules.
