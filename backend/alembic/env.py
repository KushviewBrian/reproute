from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool


from app.core.config import get_settings
from app.db.base import Base
from app.models import business, import_job, lead_score, note, route, route_candidate, saved_lead, user

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _migration_url() -> str:
    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)

    # Strip asyncpg-only query params that psycopg rejects, using string manipulation
    # to avoid make_url re-encoding the username (which can mangle project-ref dots).
    bad_keys = {"prepared_statement_cache_size", "statement_cache_size", "command_timeout", "timeout"}
    if "?" in url:
        base, qs = url.split("?", 1)
        kept = "&".join(p for p in qs.split("&") if p.split("=")[0] not in bad_keys)
        url = f"{base}?{kept}" if kept else base
    return url


def run_migrations_offline() -> None:
    url = _migration_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    config.set_main_option("sqlalchemy.url", _migration_url().replace("%", "%%"))
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
