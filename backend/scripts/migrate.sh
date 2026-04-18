#!/bin/sh
set -e

# If alembic_version table doesn't exist, the DB was set up without alembic.
# Stamp it at 0003 (last migration applied manually) so alembic only runs 0004+.
python - <<'EOF'
import sys
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from sqlalchemy import create_engine, text
from app.core.config import get_settings

BAD_KEYS = {"prepared_statement_cache_size", "statement_cache_size", "command_timeout", "timeout"}

def clean_url(url):
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if "?" not in url:
        return url
    base, qs = url.split("?", 1)
    kept = "&".join(p for p in qs.split("&") if p.split("=")[0] not in BAD_KEYS)
    return f"{base}?{kept}" if kept else base

settings = get_settings()
url = clean_url(settings.database_url)
engine = create_engine(url)
with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alembic_version')"
    ))
    exists = result.scalar()
    if not exists:
        print("alembic_version not found — stamping at 0003_saved_lead_follow_up_fields")
        sys.exit(1)
    print("alembic_version exists — skipping stamp")
    sys.exit(0)
EOF

if [ $? -ne 0 ]; then
    alembic stamp 0003_saved_lead_follow_up_fields
fi

alembic upgrade head
