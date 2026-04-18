from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


_engine = None
_SessionLocal = None
_ssl_is_secure = True


def _get_engine():
    global _engine, _SessionLocal, _ssl_is_secure
    if _engine is None:
        from app.core.config import get_settings
        settings = get_settings()
        # statement_cache_size=0 required for Supabase pgbouncer pooler
        import ssl
        ssl_ctx = ssl.create_default_context()
        if settings.database_ssl_ca_pem.strip():
            ssl_ctx.load_verify_locations(cadata=settings.database_ssl_ca_pem)
        if settings.database_tls_verify:
            ssl_ctx.check_hostname = True
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED
        else:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        _ssl_is_secure = (
            ssl_ctx.check_hostname is True and ssl_ctx.verify_mode == ssl.CERT_REQUIRED
        )
        connect_args = {
            "timeout": 10,
            "command_timeout": 10,
            "ssl": ssl_ctx,
            # Required for PgBouncer transaction/statement pooling.
            "statement_cache_size": 0,
            # Avoid duplicate statement name collisions across pooled server sessions.
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
        }
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            # App-level pooling is unnecessary with PgBouncer and can amplify statement issues.
            poolclass=NullPool,
            connect_args=connect_args,
        )
        _SessionLocal = async_sessionmaker(
            bind=_engine, class_=AsyncSession, expire_on_commit=False
        )
    return _engine, _SessionLocal


def get_engine():
    e, _ = _get_engine()
    return e


def is_db_tls_config_secure() -> bool:
    _get_engine()
    return _ssl_is_secure


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    _, SessionLocal = _get_engine()
    async with SessionLocal() as session:
        yield session
